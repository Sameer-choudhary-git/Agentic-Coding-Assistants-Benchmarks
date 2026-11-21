import { benchmarkOf } from './taskService.ts';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import type { Config } from '../config.ts';
import { PLATFORM_VERSION } from '../config.ts';
import type { Database } from '../db/database.ts';
import { badRequest, conflict, notFound, unprocessable } from '../lib/errors.ts';
import { shuffle } from '../lib/util.ts';
import type { Repositories } from '../repositories/repositories.ts';
import { ASSISTANT_IDS, type ExperimentRecord, type PlannedAttempt, type RunRecord } from '../types.ts';

export const experimentInputSchema = z.object({
  name: z.string().trim().min(3).max(120),
  description: z.string().max(4000).default(''),
  taskIds: z.array(z.string().min(1)).min(1).max(100),
  assistantIds: z.array(z.enum(ASSISTANT_IDS)).min(1).max(ASSISTANT_IDS.length),
  attempts: z.number().int().min(1).max(10),
  executionMode: z.enum(['human', 'automated']).default('human'),
  evalMode: z.enum(['docker', 'local']).optional(),
  timeLimitOverrideMinutes: z.number().int().min(1).max(240).nullable().default(null),
  randomizeOrder: z.boolean().default(true),
  seed: z
    .number()
    .int()
    .min(0)
    .max(2 ** 31 - 1)
    .optional(),
  allowUnvalidatedTasks: z.boolean().default(false),
});
export type ExperimentInput = z.infer<typeof experimentInputSchema>;

export interface ExperimentPreview {
  plannedAttempts: number;
  tasks: number;
  assistants: number;
  attempts: number;
  benchmark: string | null;
  formula: string;
  unvalidatedTasks: string[];
  unknownTasks: string[];
  evalMode: 'docker' | 'local';
  warnings: string[];
}

export class ExperimentService {
  constructor(
    private readonly cfg: Config,
    private readonly db: Database,
    private readonly repos: Repositories,
  ) {}

  preview(input: ExperimentInput): ExperimentPreview {
    const taskIds = [...new Set(input.taskIds)];
    const assistants = [...new Set(input.assistantIds)];
    const unknown = taskIds.filter((id) => !this.repos.tasks.get(id));
    const unvalidated = taskIds.filter((id) => {
      const t = this.repos.tasks.get(id);
      return t && t.validationStatus !== 'validated';
    });
    const evalMode = input.evalMode ?? this.cfg.ACB_EVAL_MODE;
    const warnings: string[] = [];
    const benchmarks = [...new Set(taskIds.map((id) => this.repos.tasks.get(id)).filter(Boolean).map((t) => benchmarkOf(t!)))];
    if (benchmarks.includes('swebench_verified') || benchmarks.includes('golden_verified')) {
      warnings.push('SWE-bench tasks are scored by the official SWE-bench harness, which needs Docker and the swebench Python package.');
    }
    if (evalMode === 'local') {
      warnings.push('Local evaluation mode runs submitted code on this machine without network or filesystem isolation.');
    }
    if (input.executionMode === 'automated') {
      warnings.push('Automated mode requires a supported headless CLI for every selected assistant; others must be run manually.');
    }
    return {
      plannedAttempts: taskIds.length * assistants.length * input.attempts,
      tasks: taskIds.length,
      assistants: assistants.length,
      attempts: input.attempts,
      formula: `${taskIds.length} tasks × ${assistants.length} assistants × ${input.attempts} attempts`,
      unvalidatedTasks: unvalidated,
      unknownTasks: unknown,
      evalMode,
      benchmark: benchmarks.length === 1 ? benchmarks[0] : benchmarks.length ? 'mixed' : null,
      warnings,
    };
  }

  create(input: ExperimentInput): { experiment: ExperimentRecord; plannedAttempts: number } {
    const preview = this.preview(input);
    if (preview.unknownTasks.length) throw badRequest('unknown task ids', preview.unknownTasks);
    if (preview.benchmark === 'mixed') {
      throw badRequest('An experiment must use one benchmark: custom tasks, SWE-bench Verified pilot tasks or golden tasks, not a mix.');
    }
    if (preview.unvalidatedTasks.length && !input.allowUnvalidatedTasks) {
      throw unprocessable(
        'Some tasks are not validated against their current content. Run task validation first, or explicitly allow unvalidated tasks (exploratory experiments only).',
        preview.unvalidatedTasks,
      );
    }
    const id = randomUUID();
    const seed = input.seed ?? Math.floor(Math.random() * 2 ** 31);
    const taskIds = [...new Set(input.taskIds)].sort();
    const assistantIds = [...new Set(input.assistantIds)];
    const tasks = taskIds.map((tid) => this.repos.tasks.get(tid)!);
    const assistants = assistantIds.map((aid) => this.repos.assistants.get(aid)!);

    const combos: Omit<PlannedAttempt, 'sequence' | 'id'>[] = [];
    for (const task of tasks) {
      const minutes = input.timeLimitOverrideMinutes ?? Number(task.metadata.timeLimitMinutes ?? 30);
      for (const assistant of assistants) {
        for (let attempt = 1; attempt <= input.attempts; attempt += 1) {
          combos.push({
            experimentId: id,
            taskId: task.id,
            taskHash: task.taskHash,
            promptHash: task.promptHash,
            assistantId: assistant.id,
            attemptNumber: attempt,
            timeLimitSeconds: minutes * 60,
          });
        }
      }
    }
    const ordered = input.randomizeOrder ? shuffle(combos, seed) : combos;
    const config = {
      platformVersion: PLATFORM_VERSION,
      plannedAttempts: preview.plannedAttempts,
      formula: preview.formula,
      executionMode: input.executionMode,
      evalMode: preview.evalMode,
      attemptsPerPair: input.attempts,
      timeLimitOverrideMinutes: input.timeLimitOverrideMinutes,
      randomizeOrder: input.randomizeOrder,
      seed,
      allowUnvalidatedTasks: input.allowUnvalidatedTasks,
      tasks: tasks.map((t) => ({
        id: t.id,
        category: t.category,
        difficulty: t.difficulty,
        version: t.version,
        testVersion: t.testVersion,
        taskHash: t.taskHash,
        promptHash: t.promptHash,
        testHash: t.testHash,
        validationStatus: t.validationStatus,
        timeLimitMinutes: input.timeLimitOverrideMinutes ?? t.metadata.timeLimitMinutes,
      })),
      assistants: assistants.map((a) => ({
        id: a.id,
        name: a.name,
        capabilityStatus: a.capabilityStatus,
        detectedVersion: a.detectedVersion,
        operatorReportedVersion: a.operatorReportedVersion,
        operatorReportedModel: a.operatorReportedModel,
        versionKnown: Boolean(a.detectedVersion || a.operatorReportedVersion),
      })),
    };
    this.db.transaction(() => {
      this.repos.experiments.insert({
        id,
        name: input.name,
        description: input.description,
        executionMode: input.executionMode,
        evalMode: preview.evalMode,
        attemptsPerPair: input.attempts,
        timeLimitOverrideMinutes: input.timeLimitOverrideMinutes,
        randomizeOrder: input.randomizeOrder,
        seed,
        config,
        createdBy: this.cfg.ACB_OPERATOR,
        machineId: this.cfg.ACB_MACHINE_ID,
      });
      ordered.forEach((combo, index) => {
        this.repos.experiments.insertPlanned({ ...combo, id: randomUUID(), sequence: index + 1 });
      });
      this.repos.events.add({
        experimentId: id,
        type: 'experiment_created',
        actor: this.cfg.ACB_OPERATOR,
        payload: { plannedAttempts: preview.plannedAttempts, formula: preview.formula },
      });
    });
    return { experiment: this.get(id), plannedAttempts: ordered.length };
  }

  get(id: string): ExperimentRecord {
    const e = this.repos.experiments.get(id);
    if (!e) throw notFound(`experiment ${id}`);
    return e;
  }

  list(): (ExperimentRecord & { progress: ReturnType<ExperimentService['progress']> })[] {
    return this.repos.experiments.list().map((e) => ({ ...e, progress: this.progress(e.id) }));
  }

  /** Materialise one run per planned attempt and mark the experiment active. */
  start(id: string): ExperimentRecord {
    const experiment = this.get(id);
    if (experiment.status !== 'planned') throw conflict(`experiment is already ${experiment.status}`);
    const planned = this.repos.experiments.planned(id);
    this.db.transaction(() => {
      for (const p of planned) {
        if (this.repos.runs.forAttempt(p.id).length) continue;
        const runId = randomUUID();
        this.repos.runs.insert({
          id: runId,
          plannedAttemptId: p.id,
          experimentId: id,
          taskId: p.taskId,
          assistantId: p.assistantId,
          attemptNumber: p.attemptNumber,
          runNumber: 1,
          retryOfRunId: null,
          status: 'planned',
          executionMode: experiment.executionMode,
          evalMode: experiment.evalMode,
          taskHash: p.taskHash,
          promptHash: p.promptHash,
          workspacePath: null,
          assistantVersion: null,
          assistantVersionSource: 'unknown',
          model: null,
          operator: this.cfg.ACB_OPERATOR,
          machineId: this.cfg.ACB_MACHINE_ID,
          timeLimitSeconds: p.timeLimitSeconds,
          preparedAt: null,
          startedAt: null,
          endedAt: null,
          submittedAt: null,
          completedAt: null,
          wallClockSeconds: null,
          timedOut: false,
          iterations: null,
          humanInterventions: null,
          notes: '',
          submissionKind: null,
          submissionHash: null,
          failureClass: null,
          errorMessage: null,
          failureModes: [],
          invalidationReason: null,
          success: null,
          outcome: null,
          latestEvaluationId: null,
        } as Omit<RunRecord, 'createdAt' | 'updatedAt'>);
      }
      this.repos.experiments.setStatus(id, 'active', 'started_at');
      this.repos.events.add({
        experimentId: id,
        type: 'experiment_started',
        actor: this.cfg.ACB_OPERATOR,
        payload: { runs: planned.length },
      });
    });
    return this.get(id);
  }

  setStatus(id: string, status: 'completed' | 'archived'): ExperimentRecord {
    const experiment = this.get(id);
    if (experiment.status === 'planned' && status === 'completed') throw conflict('experiment has not been started');
    this.repos.experiments.setStatus(id, status, status === 'completed' ? 'completed_at' : undefined);
    this.repos.events.add({ experimentId: id, type: `experiment_${status}`, actor: this.cfg.ACB_OPERATOR });
    return this.get(id);
  }

  /** Status counts over the *effective* run of each planned attempt (latest run number). */
  progress(id: string) {
    const planned = this.repos.experiments.planned(id);
    const runs = this.repos.runs.list({ experimentId: id });
    const latest = new Map<string, RunRecord>();
    for (const r of runs) {
      const cur = latest.get(r.plannedAttemptId);
      if (!cur || r.runNumber > cur.runNumber) latest.set(r.plannedAttemptId, r);
    }
    const counts: Record<string, number> = {};
    for (const r of latest.values()) counts[r.status] = (counts[r.status] ?? 0) + 1;
    const notStarted = planned.length - latest.size;
    if (notStarted > 0) counts.planned = (counts.planned ?? 0) + notStarted;
    return {
      planned: planned.length,
      totalRuns: runs.length,
      retries: runs.filter((r) => r.runNumber > 1).length,
      byStatus: counts,
      completed: counts.completed ?? 0,
      started: planned.length - (counts.planned ?? 0) - (counts.ready ?? 0),
    };
  }

  detail(id: string) {
    const experiment = this.get(id);
    const planned = this.repos.experiments.planned(id);
    const runs = this.repos.runs.list({ experimentId: id });
    return { experiment, progress: this.progress(id), plannedAttempts: planned, runs };
  }
}
