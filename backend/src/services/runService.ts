import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import type { Config } from '../config.ts';
import { type Database, nowIso } from '../db/database.ts';
import { badRequest, conflict, HttpError, notFound } from '../lib/errors.ts';
import { runProcess, safeJoin, sha256, sha256File, shortId } from '../lib/util.ts';
import type { Logger } from '../logger.ts';
import type { Repositories } from '../repositories/repositories.ts';
import { FAILURE_MODES, type RunRecord, type RunStatus } from '../types.ts';
import { executeHeadless } from './adapters/adapters.ts';
import type { AssistantService } from './assistantService.ts';
import type { EvaluatorClient } from './evaluatorClient.ts';

export const submitSchema = z.object({
  submissionType: z.enum(['workspace', 'patch', 'files']).default('workspace'),
  patch: z.string().optional(),
  files: z
    .array(z.object({ path: z.string().min(1).max(300), content: z.string().max(1_000_000) }))
    .max(200)
    .optional(),
  iterations: z.number().int().min(0).max(1000).optional(),
  humanInterventions: z.number().int().min(0).max(1000).optional(),
  notes: z.string().max(10_000).optional(),
  assistantVersion: z.string().max(120).optional(),
  model: z.string().max(120).optional(),
  autoEvaluate: z.boolean().default(true),
});
export type SubmitInput = z.infer<typeof submitSchema>;

export const logSchema = z.object({
  type: z.enum(['iteration', 'intervention', 'note']),
  note: z.string().max(2000).default(''),
});

export const labelSchema = z.object({
  failureModes: z.array(z.enum(FAILURE_MODES)).max(FAILURE_MODES.length).optional(),
  notes: z.string().max(10_000).optional(),
});

export const failSchema = z.object({
  failureClass: z.enum(['adapter_error', 'environment_error', 'operator_abort']),
  message: z.string().min(3).max(4000),
});

export const invalidateSchema = z.object({ reason: z.string().min(5).max(4000) });

/** Allowed lifecycle transitions; anything else is rejected with HTTP 409. */
const TRANSITIONS: Record<string, RunStatus[]> = {
  prepare: ['planned'],
  start: ['ready'],
  stop: ['running'],
  submit: ['running', 'awaiting_human'],
  evaluate: ['submitted', 'completed', 'failed'],
  retry: ['failed', 'invalidated'],
  fail: ['ready', 'running', 'awaiting_human', 'submitted'],
  automate: ['ready'],
  invalidate: ['planned', 'ready', 'running', 'awaiting_human', 'submitted', 'completed', 'failed'],
};

type Job = { evaluationId: string; runId: string };

export class RunService {
  private queue: Job[] = [];
  private active = 0;
  private idleWaiters: (() => void)[] = [];

  constructor(
    private readonly cfg: Config,
    private readonly db: Database,
    private readonly repos: Repositories,
    private readonly evaluator: EvaluatorClient,
    private readonly assistants: AssistantService,
    private readonly logger: Logger,
  ) {}

  // ------------------------------------------------------------------------------- helpers

  get(id: string): RunRecord {
    const run = this.repos.runs.get(id);
    if (!run) throw notFound(`run ${id}`);
    return run;
  }

  private require(run: RunRecord, action: keyof typeof TRANSITIONS): void {
    if (!TRANSITIONS[action].includes(run.status)) {
      throw conflict(`cannot ${action} a run in status '${run.status}'`, { allowed: TRANSITIONS[action] });
    }
  }

  private transition(
    run: RunRecord,
    to: RunStatus,
    patch: Partial<RunRecord>,
    type: string,
    payload: Record<string, unknown> = {},
  ): RunRecord {
    this.db.transaction(() => {
      this.repos.runs.update(run.id, { ...patch, status: to });
      this.repos.events.add({
        runId: run.id,
        experimentId: run.experimentId,
        type,
        fromStatus: run.status,
        toStatus: to,
        actor: this.cfg.ACB_OPERATOR,
        payload,
      });
    });
    return this.get(run.id);
  }

  runArtifactDir(runId: string): string {
    return safeJoin(this.cfg.ACB_ARTIFACT_ROOT, path.join('runs', runId));
  }

  private registerArtifact(run: RunRecord, file: string, kind: string, evaluationId: string | null = null): void {
    const rel = path.relative(this.cfg.ACB_ARTIFACT_ROOT, file).split(path.sep).join('/');
    this.repos.artifacts.add({
      runId: run.id,
      evaluationId,
      kind,
      relativePath: rel,
      sizeBytes: fs.statSync(file).size,
      sha256: sha256File(file),
    });
  }

  private ensureExperimentActive(run: RunRecord): void {
    const e = this.repos.experiments.get(run.experimentId);
    if (e && e.status !== 'active') throw conflict(`experiment is ${e.status}; runs can only change while it is active`);
  }

  // ------------------------------------------------------------------------------ lifecycle

  /** Create a clean workspace (starter files only) outside the repository. */
  async prepare(id: string): Promise<RunRecord> {
    const run = this.get(id);
    this.require(run, 'prepare');
    this.ensureExperimentActive(run);
    const task = this.repos.tasks.get(run.taskId);
    if (!task) throw notFound(`task ${run.taskId}`);
    if (task.taskHash !== run.taskHash) {
      throw conflict(
        'the task definition changed after this experiment was created; the frozen task version is no longer available on disk',
        {
          expected: run.taskHash,
          current: task.taskHash,
        },
      );
    }
    const dir = path.join(this.cfg.ACB_WORKSPACE_ROOT, shortId(run.experimentId), `${run.taskId}_${shortId(run.id)}_r${run.runNumber}`);
    if (fs.existsSync(dir) && fs.readdirSync(dir).length) throw conflict(`workspace directory already exists: ${dir}`);
    await this.evaluator.createWorkspace(run.taskId, dir);
    const git = await this.initGit(dir);
    return this.transition(run, 'ready', { workspacePath: dir, preparedAt: nowIso() }, 'workspace_prepared', { workspace: dir, git });
  }

  private async initGit(dir: string): Promise<string> {
    const opts = { cwd: dir, timeoutMs: 30_000 };
    const init = await runProcess('git', ['init', '-q'], opts);
    if (init.code !== 0) return `git unavailable: ${init.error ?? init.stderr.trim()}`;
    await runProcess('git', ['add', '-A'], opts);
    const commit = await runProcess(
      'git',
      ['-c', 'user.name=acb', '-c', 'user.email=acb@localhost', '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'starter'],
      opts,
    );
    return commit.code === 0 ? 'initialised with starter commit' : `git commit failed: ${commit.stderr.trim()}`;
  }

  start(id: string, body: { assistantVersion?: string; model?: string } = {}): RunRecord {
    const run = this.get(id);
    this.require(run, 'start');
    this.ensureExperimentActive(run);
    return this.transition(
      run,
      'running',
      {
        startedAt: nowIso(),
        executionMode: 'human',
        iterations: 1,
        humanInterventions: 0,
        ...this.versionPatch(run, body.assistantVersion, body.model),
      },
      'run_started',
      { mode: run.executionMode },
    );
  }

  private versionPatch(run: RunRecord, version?: string, model?: string): Partial<RunRecord> {
    if (version) return { assistantVersion: version, assistantVersionSource: 'operator', model: model ?? run.model };
    if (run.assistantVersion) return model ? { model } : {};
    const a = this.repos.assistants.get(run.assistantId);
    if (a?.operatorReportedVersion) {
      return { assistantVersion: a.operatorReportedVersion, assistantVersionSource: 'operator', model: model ?? a.operatorReportedModel };
    }
    if (a?.detectedVersion) return { assistantVersion: a.detectedVersion, assistantVersionSource: 'detected', model: model ?? null };
    return { assistantVersionSource: 'unknown', model: model ?? null };
  }

  logActivity(id: string, input: z.infer<typeof logSchema>): RunRecord {
    const run = this.get(id);
    if (run.status !== 'running' && run.status !== 'awaiting_human') {
      throw conflict(`activity can only be logged while a run is in progress (status '${run.status}')`);
    }
    const patch: Partial<RunRecord> = {};
    if (input.type === 'iteration') patch.iterations = (run.iterations ?? 0) + 1;
    if (input.type === 'intervention') patch.humanInterventions = (run.humanInterventions ?? 0) + 1;
    this.db.transaction(() => {
      if (Object.keys(patch).length) this.repos.runs.update(id, patch);
      this.repos.events.add({
        runId: id,
        experimentId: run.experimentId,
        type: `logged_${input.type}`,
        actor: this.cfg.ACB_OPERATOR,
        payload: { note: input.note },
      });
    });
    return this.get(id);
  }

  private wallClock(run: RunRecord, end: string): { wallClockSeconds: number | null; timedOut: boolean } {
    if (!run.startedAt) return { wallClockSeconds: null, timedOut: false };
    const seconds = Math.max(0, (Date.parse(end) - Date.parse(run.startedAt)) / 1000);
    return { wallClockSeconds: Math.round(seconds * 10) / 10, timedOut: seconds > run.timeLimitSeconds };
  }

  stop(id: string): RunRecord {
    const run = this.get(id);
    this.require(run, 'stop');
    const end = nowIso();
    return this.transition(run, 'awaiting_human', { endedAt: end, ...this.wallClock(run, end) }, 'run_stopped');
  }

  async submit(id: string, input: SubmitInput): Promise<RunRecord> {
    const run = this.get(id);
    this.require(run, 'submit');
    if (!run.workspacePath || !fs.existsSync(run.workspacePath)) throw conflict('workspace directory is missing');
    const dir = this.runArtifactDir(run.id);
    fs.mkdirSync(dir, { recursive: true });

    if (input.submissionType === 'patch') {
      await this.applyPatch(run, input.patch ?? '', dir);
    } else if (input.submissionType === 'files') {
      this.writeFiles(run, input.files ?? []);
    }

    const end = run.endedAt ?? nowIso();
    const clock = run.endedAt ? { wallClockSeconds: run.wallClockSeconds, timedOut: run.timedOut } : this.wallClock(run, end);
    const notes = [run.notes, input.notes].filter(Boolean).join('\n');
    const updated = this.transition(
      run,
      'submitted',
      {
        endedAt: end,
        submittedAt: nowIso(),
        ...clock,
        submissionKind: input.submissionType,
        iterations: input.iterations ?? run.iterations,
        humanInterventions: input.humanInterventions ?? run.humanInterventions,
        notes,
        ...this.versionPatch(run, input.assistantVersion, input.model),
      },
      'run_submitted',
      { submissionType: input.submissionType, iterations: input.iterations, humanInterventions: input.humanInterventions },
    );
    if (input.autoEvaluate) this.enqueueEvaluation(updated.id);
    return this.get(updated.id);
  }

  private async applyPatch(run: RunRecord, patch: string, dir: string): Promise<void> {
    if (!patch.trim()) throw badRequest('patch is empty');
    if (Buffer.byteLength(patch, 'utf8') > this.cfg.ACB_MAX_PATCH_BYTES)
      throw new HttpError(413, 'payload_too_large', 'patch is too large');
    const paths = [...patch.matchAll(/^(?:\+\+\+|---) (?:[ab]\/)?(\S+)/gm)].map((m) => m[1]).filter((p) => p !== '/dev/null');
    for (const p of paths) {
      try {
        safeJoin(run.workspacePath!, p);
      } catch {
        throw badRequest(`patch touches a path outside the workspace: ${p}`);
      }
    }
    const file = path.join(dir, `submitted-${Date.now()}.patch`);
    fs.writeFileSync(file, patch, 'utf8');
    this.registerArtifact(run, file, 'submitted_patch');
    const opts = { cwd: run.workspacePath!, timeoutMs: 60_000 };
    const check = await runProcess('git', ['apply', '--check', '--whitespace=nowarn', file], opts);
    if (check.error) throw new HttpError(422, 'git_unavailable', `git is required to apply patches: ${check.error}`);
    if (check.code !== 0) throw new HttpError(422, 'patch_rejected', `patch does not apply cleanly: ${check.stderr.trim().slice(0, 2000)}`);
    const apply = await runProcess('git', ['apply', '--whitespace=nowarn', file], opts);
    if (apply.code !== 0) throw new HttpError(422, 'patch_rejected', `git apply failed: ${apply.stderr.trim().slice(0, 2000)}`);
  }

  private writeFiles(run: RunRecord, files: { path: string; content: string }[]): void {
    if (!files.length) throw badRequest('no files supplied');
    const targets = files.map((f) => {
      try {
        return { target: safeJoin(run.workspacePath!, f.path), content: f.content };
      } catch {
        throw badRequest(`file path outside the workspace: ${f.path}`);
      }
    });
    for (const { target, content } of targets) {
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, content, 'utf8');
    }
  }

  // ----------------------------------------------------------------------------- evaluation

  enqueueEvaluation(id: string): { evaluationId: string; run: RunRecord } {
    const run = this.get(id);
    this.require(run, 'evaluate');
    if (run.status === 'failed' && run.failureClass !== 'evaluator_error') {
      throw conflict('only runs that failed because of an evaluator error can be re-evaluated; retry the attempt instead');
    }
    if (!run.workspacePath || !fs.existsSync(run.workspacePath)) throw conflict('workspace directory is missing');
    const evaluation = this.repos.evaluations.create(run.id, run.evalMode);
    const updated = this.transition(run, 'evaluating', { latestEvaluationId: evaluation.id }, 'evaluation_queued', {
      evaluationId: evaluation.id,
    });
    this.queue.push({ evaluationId: evaluation.id, runId: run.id });
    setImmediate(() => this.pump());
    return { evaluationId: evaluation.id, run: updated };
  }

  /** Resolves when the evaluation queue is empty (used by tests and graceful shutdown). */
  idle(): Promise<void> {
    if (!this.queue.length && this.active === 0) return Promise.resolve();
    return new Promise((resolve) => this.idleWaiters.push(resolve));
  }

  private pump(): void {
    while (this.active < this.cfg.ACB_EVAL_CONCURRENCY && this.queue.length) {
      const job = this.queue.shift()!;
      this.active += 1;
      this.process(job)
        .catch((err) => this.logger.error('evaluation job crashed', { runId: job.runId, error: String(err) }))
        .finally(() => {
          this.active -= 1;
          if (!this.queue.length && this.active === 0) this.idleWaiters.splice(0).forEach((r) => r());
          else this.pump();
        });
    }
  }

  private async process(job: Job): Promise<void> {
    const run = this.get(job.runId);
    const outDir = path.join(this.runArtifactDir(run.id), 'evaluations', job.evaluationId);
    this.repos.evaluations.markRunning(job.evaluationId, path.relative(this.cfg.ACB_ARTIFACT_ROOT, outDir).split(path.sep).join('/'));
    this.logger.info('evaluation started', { runId: run.id, evaluationId: job.evaluationId, task: run.taskId });
    let report: Record<string, any>;
    try {
      report = await this.evaluator.evaluate({
        taskId: run.taskId,
        workspace: run.workspacePath!,
        outDir,
        mode: run.evalMode,
        expectedTaskHash: run.taskHash,
        timeoutSeconds: this.repos.tasks.get(run.taskId)?.kind === 'swebench' ? this.cfg.ACB_SWEBENCH_EVAL_TIMEOUT_SECONDS : undefined,
        context: {
          run_id: run.id,
          experiment_id: run.experimentId,
          assistant_id: run.assistantId,
          attempt_number: run.attemptNumber,
          run_number: run.runNumber,
        },
      });
    } catch (err) {
      this.finishWithError(run, job.evaluationId, 'evaluator_unavailable', (err as Error).message);
      return;
    }
    this.ingest(run, job.evaluationId, report, outDir);
  }

  private finishWithError(run: RunRecord, evaluationId: string, errorClass: string, message: string): void {
    this.db.transaction(() => {
      this.repos.evaluations.finish(evaluationId, { status: 'error', error_class: errorClass, error_message: message.slice(0, 4000) });
      this.repos.runs.update(run.id, {
        status: 'failed',
        failureClass: 'evaluator_error',
        errorMessage: message.slice(0, 4000),
        success: null,
        outcome: 'evaluator_error',
      });
      this.repos.events.add({
        runId: run.id,
        experimentId: run.experimentId,
        type: 'evaluation_error',
        fromStatus: 'evaluating',
        toStatus: 'failed',
        actor: 'evaluator',
        payload: { errorClass, message: message.slice(0, 1000) },
      });
    });
    this.logger.warn('evaluation failed', { runId: run.id, errorClass, message: message.slice(0, 500) });
  }

  private ingest(run: RunRecord, evaluationId: string, report: Record<string, any>, outDir: string): void {
    const acc = report.acceptance ?? {};
    const reg = report.regression ?? {};
    const ruff = report.ruff ?? {};
    const sem = report.semgrep ?? {};
    const diff = report.diff ?? {};
    const tq = report.test_quality ?? null;
    const completed = report.status === 'completed';
    const evalSuccess: boolean | null = completed ? Boolean(report.success) : null;
    const env = report.environment ?? {};
    const toolVersions = {
      evaluator: report.evaluator_version,
      host_python: env.host_python,
      execution: env.execution ?? null,
      ruff: ruff.version ?? null,
      semgrep: sem.version ?? null,
    };
    const num = (v: unknown) => (typeof v === 'number' ? v : null);
    this.db.transaction(() => {
      this.repos.evaluations.finish(evaluationId, {
        status: completed ? 'completed' : 'error',
        evaluator_version: report.evaluator_version ?? null,
        success: evalSuccess === null ? null : evalSuccess ? 1 : 0,
        outcome: report.outcome ?? null,
        error_class: report.error?.class ?? null,
        error_message: report.error?.message ?? null,
        acceptance_passed: num(acc.passed),
        acceptance_failed: num(acc.failed),
        acceptance_errors: num(acc.errors),
        acceptance_total: num(acc.total),
        acceptance_expected: num(acc.expected_total),
        regression_passed: num(reg.passed),
        regression_failed: num(reg.failed),
        regression_errors: num(reg.errors),
        regression_total: num(reg.total),
        ruff_status: ruff.status ?? null,
        ruff_count: num(ruff.submission_count),
        ruff_new: num(ruff.new_count),
        semgrep_status: sem.status ?? null,
        semgrep_count: num(sem.submission_count),
        semgrep_new: num(sem.new_count),
        semgrep_resolved: num(sem.resolved_count),
        line_coverage: tq ? num(tq.line_coverage) : null,
        mutation_score: tq ? num(tq.mutation_score) : null,
        files_changed: num(diff.files_changed),
        lines_added: num(diff.lines_added),
        lines_removed: num(diff.lines_removed),
        out_of_scope_count: Array.isArray(diff.out_of_scope_files) ? diff.out_of_scope_files.length : null,
        duration_seconds: num(report.duration_s),
        tool_versions_json: JSON.stringify(toolVersions),
      });
      const suites: [string, any[]][] = [
        [tq ? 'quality' : 'acceptance', acc.tests ?? []],
        ['regression', reg.tests ?? []],
      ];
      for (const [suite, tests] of suites) {
        for (const t of tests.slice(0, 1000)) {
          this.repos.evaluations.addTestOutcome(
            evaluationId,
            suite,
            String(t.id),
            String(t.outcome),
            num(t.duration_s),
            t.message ? String(t.message).slice(0, 2000) : null,
          );
        }
      }
      const newRuff = new Set((ruff.new_findings ?? []).map((f: any) => JSON.stringify([f.path, f.code, f.message, f.line])));
      for (const f of (ruff.findings ?? []).slice(0, 500)) {
        this.repos.evaluations.addFinding(evaluationId, {
          tool: 'ruff',
          ruleId: String(f.code),
          severity: f.category ?? null,
          path: f.path ?? null,
          line: num(f.line),
          message: f.message ?? null,
          isNew: newRuff.has(JSON.stringify([f.path, f.code, f.message, f.line])),
        });
      }
      const newSem = new Set((sem.new_findings ?? []).map((f: any) => JSON.stringify([f.path, f.rule_id, f.line])));
      for (const f of (sem.findings ?? []).slice(0, 500)) {
        this.repos.evaluations.addFinding(evaluationId, {
          tool: 'semgrep',
          ruleId: String(f.rule_id),
          severity: f.severity ?? null,
          path: f.path ?? null,
          line: num(f.line),
          message: f.message ?? null,
          isNew: newSem.has(JSON.stringify([f.path, f.rule_id, f.line])),
        });
      }
      if (fs.existsSync(outDir)) {
        for (const name of fs.readdirSync(outDir)) {
          const file = path.join(outDir, name);
          if (fs.statSync(file).isFile()) this.registerArtifact(run, file, `evaluation:${name}`, evaluationId);
        }
      }
      if (completed) {
        // Run-level success applies the time-limit rule on top of the evaluator's verdict.
        const current = this.get(run.id);
        const success = Boolean(evalSuccess) && !current.timedOut;
        const failureClass = success ? null : current.timedOut ? 'timeout' : 'task_failure';
        this.repos.runs.update(run.id, {
          status: 'completed',
          completedAt: nowIso(),
          success,
          outcome: current.timedOut ? 'time_limit_exceeded' : report.outcome,
          failureClass,
          errorMessage: null,
          submissionHash: report.workspace?.snapshot_hash ?? null,
        });
        this.repos.events.add({
          runId: run.id,
          experimentId: run.experimentId,
          type: 'evaluation_completed',
          fromStatus: 'evaluating',
          toStatus: 'completed',
          actor: 'evaluator',
          payload: { evaluationId, success, outcome: report.outcome },
        });
      }
    });
    if (!completed) {
      this.finishWithError(
        run,
        evaluationId,
        report.error?.class ?? 'evaluator_error',
        report.error?.message ?? 'evaluation did not complete',
      );
      return;
    }
    this.logger.info('evaluation completed', { runId: run.id, evaluationId, outcome: report.outcome, success: report.success });
  }

  // ---------------------------------------------------------------------- other transitions

  retry(id: string): RunRecord {
    const run = this.get(id);
    this.require(run, 'retry');
    this.ensureExperimentActive(run);
    const siblings = this.repos.runs.forAttempt(run.plannedAttemptId);
    const latest = siblings[siblings.length - 1];
    if (latest.id !== run.id) throw conflict('only the latest run of an attempt can be retried', { latestRunId: latest.id });
    const newId = randomUUID();
    this.db.transaction(() => {
      this.repos.runs.insert({
        ...run,
        id: newId,
        runNumber: run.runNumber + 1,
        retryOfRunId: run.id,
        status: 'planned',
        workspacePath: null,
        assistantVersion: null,
        assistantVersionSource: 'unknown',
        model: null,
        operator: this.cfg.ACB_OPERATOR,
        machineId: this.cfg.ACB_MACHINE_ID,
        notes: '',
        failureModes: [],
      });
      this.repos.events.add({
        runId: run.id,
        experimentId: run.experimentId,
        type: 'run_retried',
        actor: this.cfg.ACB_OPERATOR,
        payload: { newRunId: newId },
      });
      this.repos.events.add({
        runId: newId,
        experimentId: run.experimentId,
        type: 'run_created_as_retry',
        toStatus: 'planned',
        actor: this.cfg.ACB_OPERATOR,
        payload: { retryOf: run.id },
      });
    });
    return this.get(newId);
  }

  fail(id: string, input: z.infer<typeof failSchema>): RunRecord {
    const run = this.get(id);
    this.require(run, 'fail');
    const end = nowIso();
    return this.transition(
      run,
      'failed',
      {
        failureClass: input.failureClass,
        errorMessage: input.message,
        endedAt: run.endedAt ?? end,
        success: null,
        outcome: input.failureClass,
      },
      'run_failed',
      { failureClass: input.failureClass, message: input.message },
    );
  }

  invalidate(id: string, reason: string): RunRecord {
    const run = this.get(id);
    this.require(run, 'invalidate');
    if (run.status === 'evaluating') throw conflict('wait for the evaluation to finish before invalidating');
    return this.transition(run, 'invalidated', { invalidationReason: reason }, 'run_invalidated', { reason, previousSuccess: run.success });
  }

  label(id: string, input: z.infer<typeof labelSchema>): RunRecord {
    const run = this.get(id);
    const patch: Partial<RunRecord> = {};
    if (input.failureModes) patch.failureModes = input.failureModes;
    if (input.notes !== undefined) patch.notes = input.notes;
    this.db.transaction(() => {
      this.repos.runs.update(id, patch);
      this.repos.events.add({
        runId: id,
        experimentId: run.experimentId,
        type: 'run_labelled',
        actor: this.cfg.ACB_OPERATOR,
        payload: { failureModes: input.failureModes },
      });
    });
    return this.get(id);
  }

  /** Run a supported headless CLI in the workspace, then evaluate whatever it produced. */
  async automate(id: string): Promise<RunRecord> {
    const run = this.get(id);
    this.require(run, 'automate');
    this.ensureExperimentActive(run);
    const report = await this.assistants.report(run.assistantId);
    if (report.status !== 'supported' || !report.command) {
      throw conflict(`automated execution is not available for ${run.assistantId}: ${report.status}`, { detail: report.detail });
    }
    const task = this.repos.tasks.get(run.taskId)!;
    const prompt = this.repos.tasks.versionPrompt(run.taskId, run.taskHash) ?? task.prompt;
    const dir = this.runArtifactDir(run.id);
    fs.mkdirSync(dir, { recursive: true });
    const promptFile = path.join(dir, 'prompt.md');
    fs.writeFileSync(promptFile, prompt, 'utf8');
    const startedAt = nowIso();
    const running = this.transition(
      run,
      'running',
      {
        startedAt,
        executionMode: 'automated',
        iterations: 1,
        humanInterventions: 0,
        assistantVersion: report.detectedVersion,
        assistantVersionSource: report.detectedVersion ? 'detected' : 'unknown',
      },
      'adapter_started',
      { command: report.command.map((c) => (c === prompt ? '{prompt}' : c)) },
    );
    const result = await executeHeadless(report.command, {
      prompt,
      promptFile,
      workspace: run.workspacePath!,
      timeoutMs: run.timeLimitSeconds * 1000,
    });
    for (const [name, content] of [
      ['adapter.stdout.txt', result.stdout],
      ['adapter.stderr.txt', result.stderr],
    ] as const) {
      const file = path.join(dir, name);
      fs.writeFileSync(file, content, 'utf8');
      this.registerArtifact(running, file, 'adapter_output');
    }
    const end = nowIso();
    const clock = this.wallClock(running, end);
    if (result.error || (!result.timedOut && result.exitCode !== 0)) {
      return this.transition(
        this.get(id),
        'failed',
        {
          endedAt: end,
          ...clock,
          failureClass: 'adapter_error',
          errorMessage: (result.error ?? `exit code ${result.exitCode}: ${result.stderr.slice(-1000)}`).slice(0, 4000),
        },
        'adapter_failed',
        { exitCode: result.exitCode, error: result.error },
      );
    }
    const submitted = this.transition(
      this.get(id),
      'submitted',
      {
        endedAt: end,
        submittedAt: end,
        wallClockSeconds: clock.wallClockSeconds,
        timedOut: result.timedOut || clock.timedOut,
        submissionKind: 'workspace',
      },
      'adapter_finished',
      { exitCode: result.exitCode, timedOut: result.timedOut, durationMs: result.durationMs, digest: sha256(result.stdout).slice(0, 16) },
    );
    this.enqueueEvaluation(submitted.id);
    return this.get(id);
  }

  detail(id: string) {
    const run = this.get(id);
    const evaluations = this.repos.evaluations.forRun(id);
    const latest = run.latestEvaluationId ? this.repos.evaluations.get(run.latestEvaluationId) : undefined;
    const task = this.repos.tasks.get(run.taskId);
    const prompt = this.repos.tasks.versionPrompt(run.taskId, run.taskHash) ?? task?.prompt ?? '';
    return {
      run,
      task: task
        ? { id: task.id, title: task.title, category: task.category, difficulty: task.difficulty, version: task.version, kind: task.kind }
        : null,
      prompt,
      promptHash: run.promptHash,
      assistant: this.repos.assistants.get(run.assistantId),
      evaluations,
      latestEvaluation: latest ?? null,
      testOutcomes: latest ? this.repos.evaluations.testOutcomes(latest.id) : [],
      findings: latest ? this.repos.evaluations.findings(latest.id) : [],
      artifacts: this.repos.artifacts.forRun(id),
      events: this.repos.events.forRun(id),
      siblings: this.repos.runs.forAttempt(run.plannedAttemptId).map((r) => ({ id: r.id, runNumber: r.runNumber, status: r.status })),
    };
  }

  artifactPath(runId: string, artifactId: string): { file: string; name: string } {
    const artifact = this.repos.artifacts.get(artifactId);
    if (!artifact || artifact.runId !== runId) throw notFound('artifact');
    const file = safeJoin(this.cfg.ACB_ARTIFACT_ROOT, artifact.relativePath);
    if (!fs.existsSync(file)) throw notFound('artifact file');
    return { file, name: path.basename(file) };
  }

  /**
   * Called on startup: evaluations interrupted by a restart are marked as errors and their runs go
   * back to 'submitted' so they can be re-evaluated; automated runs interrupted mid-execution fail.
   */
  recoverInterrupted(): { evaluations: number; runs: number } {
    let evaluations = 0;
    let runs = 0;
    this.db.transaction(() => {
      for (const ev of this.repos.evaluations.byStatus(['queued', 'running'])) {
        this.repos.evaluations.finish(ev.id, {
          status: 'error',
          error_class: 'interrupted',
          error_message: 'server restarted during evaluation',
        });
        evaluations += 1;
      }
      for (const run of this.repos.runs.byStatus(['evaluating'])) {
        this.repos.runs.update(run.id, { status: 'submitted' });
        this.repos.events.add({
          runId: run.id,
          experimentId: run.experimentId,
          type: 'evaluation_interrupted',
          fromStatus: 'evaluating',
          toStatus: 'submitted',
          actor: 'system',
        });
        runs += 1;
      }
      for (const run of this.repos.runs.byStatus(['running'])) {
        if (run.executionMode !== 'automated') continue;
        this.repos.runs.update(run.id, {
          status: 'failed',
          failureClass: 'adapter_error',
          errorMessage: 'server restarted while the adapter was running',
        });
        this.repos.events.add({
          runId: run.id,
          experimentId: run.experimentId,
          type: 'adapter_interrupted',
          fromStatus: 'running',
          toStatus: 'failed',
          actor: 'system',
        });
        runs += 1;
      }
    });
    return { evaluations, runs };
  }
}
