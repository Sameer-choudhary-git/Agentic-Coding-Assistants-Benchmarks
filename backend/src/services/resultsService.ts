/**
 * Metric computation. All numbers are derived from persisted run and evaluation records; nothing is
 * estimated or filled in. Formulas and denominators are documented in
 * docs/metrics-and-data-dictionary.md and mirrored in DATA_DICTIONARY below.
 */
import { benchmarkOf } from './taskService.ts';
import type { Repositories } from '../repositories/repositories.ts';
import type { EvaluationRecord, RunRecord } from '../types.ts';
import { mean, median, quantile, wilson } from '../lib/util.ts';

export interface FlatRecord {
  experiment_id: string;
  experiment_name: string;
  planned_attempt_id: string;
  run_id: string;
  run_number: number;
  retry_of_run_id: string | null;
  is_effective_run: boolean;
  task_id: string;
  task_category: string;
  task_difficulty: string;
  task_kind: string;
  task_benchmark: string;
  task_version: string;
  test_version: string;
  task_hash: string;
  prompt_hash: string;
  assistant_id: string;
  assistant_version: string | null;
  assistant_version_source: string;
  model: string | null;
  attempt_number: number;
  execution_mode: string;
  eval_mode: string;
  operator: string;
  machine_id: string;
  status: string;
  failure_class: string | null;
  outcome: string | null;
  success: boolean | null;
  evaluation_success: boolean | null;
  eligible_for_success: boolean;
  timed_out: boolean;
  prepared_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  wall_clock_seconds: number | null;
  time_limit_seconds: number;
  iterations: number | null;
  human_interventions: number | null;
  acceptance_passed: number | null;
  acceptance_failed: number | null;
  acceptance_errors: number | null;
  acceptance_total: number | null;
  acceptance_expected: number | null;
  regression_failed: number | null;
  regression_errors: number | null;
  regression_total: number | null;
  regression_failure: boolean | null;
  line_coverage: number | null;
  mutation_score: number | null;
  ruff_status: string | null;
  ruff_count: number | null;
  ruff_new: number | null;
  semgrep_status: string | null;
  semgrep_count: number | null;
  semgrep_new: number | null;
  semgrep_resolved: number | null;
  files_changed: number | null;
  lines_added: number | null;
  lines_removed: number | null;
  out_of_scope_count: number | null;
  evaluation_id: string | null;
  evaluator_version: string | null;
  evaluation_duration_seconds: number | null;
  submission_hash: string | null;
  failure_modes: string;
  invalidation_reason: string | null;
  notes: string;
}

export const DATA_DICTIONARY: { field: keyof FlatRecord; type: string; description: string }[] = [
  { field: 'experiment_id', type: 'uuid', description: 'Experiment identifier.' },
  { field: 'experiment_name', type: 'string', description: 'Human-readable experiment name.' },
  { field: 'planned_attempt_id', type: 'uuid', description: 'One cell of the experiment matrix (task × assistant × attempt number).' },
  {
    field: 'run_id',
    type: 'uuid',
    description: 'One execution of a planned attempt. Retries create new run ids; history is never overwritten.',
  },
  { field: 'run_number', type: 'int', description: '1 for the original run, 2+ for retries of the same planned attempt.' },
  {
    field: 'retry_of_run_id',
    type: 'uuid|null',
    description: 'Run that this run retries (only operational failures or invalidated runs can be retried).',
  },
  {
    field: 'is_effective_run',
    type: 'bool',
    description: 'True for the latest run of each planned attempt; only effective runs enter aggregate metrics.',
  },
  { field: 'task_id', type: 'string', description: 'Task identifier, e.g. BF-01 or a SWE-bench instance id such as django__django-16661.' },
  {
    field: 'task_category',
    type: 'enum',
    description: 'bug_fixing | feature_implementation | security_remediation | refactoring | test_writing | repository_reasoning | swebench_verified | performance (golden tasks use their dataset domain).',
  },
  { field: 'task_difficulty', type: 'enum', description: 'easy | medium | hard (criteria in docs/experimental-protocol.md).' },
  { field: 'task_kind', type: 'enum', description: 'standard (hidden acceptance tests), test_writing (coverage + mutation checks) or swebench (official SWE-bench harness).' },
  { field: 'task_benchmark', type: 'enum', description: 'custom (the 18-task suite), swebench_verified (pilot issues) or golden_verified (golden-dataset issues); both SWE-bench benchmarks use the official harness.' },
  { field: 'task_version', type: 'semver', description: 'Task metadata version.' },
  { field: 'test_version', type: 'semver', description: 'Hidden test-suite version.' },
  {
    field: 'task_hash',
    type: 'sha256',
    description: 'Hash of task.json, prompt, starter files and hidden tests when the experiment was created.',
  },
  { field: 'prompt_hash', type: 'sha256', description: 'Hash of the frozen prompt shown to the assistant.' },
  { field: 'assistant_id', type: 'enum', description: 'copilot | cursor | claude_code | codex.' },
  {
    field: 'assistant_version',
    type: 'string|null',
    description: 'Assistant/CLI version if detected or reported by the operator; null when unknown (never guessed).',
  },
  { field: 'assistant_version_source', type: 'enum', description: 'detected (CLI --version) | operator (typed by researcher) | unknown.' },
  { field: 'model', type: 'string|null', description: 'Underlying model as reported by the operator, when known.' },
  { field: 'attempt_number', type: 'int', description: 'Attempt index within the task × assistant pair (1..attempts).' },
  { field: 'execution_mode', type: 'enum', description: 'human (operator-driven) or automated (headless CLI adapter).' },
  { field: 'eval_mode', type: 'enum', description: 'docker (sandboxed) or local (host subprocess) evaluation.' },
  { field: 'operator', type: 'string', description: 'Researcher who executed the run (ACB_OPERATOR).' },
  { field: 'machine_id', type: 'string', description: 'Machine on which the run was executed (ACB_MACHINE_ID).' },
  {
    field: 'status',
    type: 'enum',
    description: 'planned | ready | running | awaiting_human | submitted | evaluating | completed | failed | invalidated.',
  },
  {
    field: 'failure_class',
    type: 'enum|null',
    description: 'task_failure | timeout | evaluator_error | adapter_error | environment_error | operator_abort. Null for successful runs.',
  },
  {
    field: 'outcome',
    type: 'string|null',
    description: 'Evaluator outcome (passed, acceptance_failed, regression_failed, test_timeout, collection_error) or time_limit_exceeded.',
  },
  {
    field: 'success',
    type: 'bool|null',
    description:
      'Run-level functional success = evaluator success AND within the time limit. Null when the run never completed evaluation.',
  },
  { field: 'evaluation_success', type: 'bool|null', description: 'Raw evaluator verdict, ignoring the time limit.' },
  {
    field: 'eligible_for_success',
    type: 'bool',
    description: 'Effective run with status completed. Only eligible runs form the success-rate denominator.',
  },
  { field: 'timed_out', type: 'bool', description: 'Wall-clock duration exceeded the time limit (counted as a functional failure).' },
  { field: 'prepared_at', type: 'iso8601|null', description: 'Workspace creation time.' },
  { field: 'started_at', type: 'iso8601|null', description: 'Start of the assistant session.' },
  { field: 'ended_at', type: 'iso8601|null', description: 'End of the assistant session.' },
  { field: 'submitted_at', type: 'iso8601|null', description: 'Submission time.' },
  { field: 'completed_at', type: 'iso8601|null', description: 'Evaluation completion time.' },
  {
    field: 'wall_clock_seconds',
    type: 'float|null',
    description: 'ended_at − started_at in seconds (assistant session duration, excludes evaluation).',
  },
  { field: 'time_limit_seconds', type: 'int', description: 'Time budget for the attempt.' },
  {
    field: 'iterations',
    type: 'int|null',
    description: 'Number of prompts sent to the assistant (initial prompt = 1). See protocol for the exact definition.',
  },
  {
    field: 'human_interventions',
    type: 'int|null',
    description: 'Number of human actions beyond prompting (manual edits, approvals, corrective hints). See protocol.',
  },
  { field: 'acceptance_passed', type: 'int|null', description: 'Hidden acceptance tests (or quality checks) passed.' },
  { field: 'acceptance_failed', type: 'int|null', description: 'Acceptance tests failed.' },
  { field: 'acceptance_errors', type: 'int|null', description: 'Acceptance tests that errored.' },
  { field: 'acceptance_total', type: 'int|null', description: 'Acceptance tests collected.' },
  {
    field: 'acceptance_expected',
    type: 'int|null',
    description: 'Acceptance tests expected from task validation (missing tests count as not passed).',
  },
  { field: 'regression_failed', type: 'int|null', description: 'Hidden regression tests failed.' },
  { field: 'regression_errors', type: 'int|null', description: 'Hidden regression tests errored.' },
  { field: 'regression_total', type: 'int|null', description: 'Hidden regression tests collected.' },
  { field: 'regression_failure', type: 'bool|null', description: 'At least one regression test failed or errored.' },
  {
    field: 'line_coverage',
    type: 'float|null',
    description: 'Test-writing tasks: line coverage of the target module by the submitted tests (0–1).',
  },
  { field: 'mutation_score', type: 'float|null', description: 'Test-writing tasks: fraction of hidden mutants detected (0–1).' },
  { field: 'ruff_status', type: 'enum|null', description: 'ran | unavailable | error. Unavailable is never treated as zero findings.' },
  { field: 'ruff_count', type: 'int|null', description: 'Ruff findings in the submitted workspace.' },
  { field: 'ruff_new', type: 'int|null', description: 'Ruff findings not present in the starter baseline.' },
  { field: 'semgrep_status', type: 'enum|null', description: 'ran | unavailable | error.' },
  { field: 'semgrep_count', type: 'int|null', description: 'Semgrep findings in the submitted workspace.' },
  { field: 'semgrep_new', type: 'int|null', description: 'Semgrep findings introduced relative to the starter baseline.' },
  { field: 'semgrep_resolved', type: 'int|null', description: 'Baseline Semgrep findings no longer present.' },
  { field: 'files_changed', type: 'int|null', description: 'Files added, modified or deleted relative to the starter.' },
  { field: 'lines_added', type: 'int|null', description: 'Added lines in the submission diff.' },
  { field: 'lines_removed', type: 'int|null', description: 'Removed lines in the submission diff.' },
  { field: 'out_of_scope_count', type: 'int|null', description: 'Changed files outside the task scope (allowed_paths).' },
  { field: 'evaluation_id', type: 'uuid|null', description: 'Latest evaluation of the run.' },
  { field: 'evaluator_version', type: 'string|null', description: 'Evaluator version that produced the result.' },
  { field: 'evaluation_duration_seconds', type: 'float|null', description: 'Evaluator runtime.' },
  { field: 'submission_hash', type: 'sha256|null', description: 'Hash of the evaluated workspace snapshot.' },
  { field: 'failure_modes', type: 'string', description: 'Semicolon-separated failure-mode labels assigned by researchers.' },
  { field: 'invalidation_reason', type: 'string|null', description: 'Why the run was invalidated (protocol violation etc.).' },
  { field: 'notes', type: 'string', description: 'Operator notes.' },
];

function effective(runs: RunRecord[]): Set<string> {
  const latest = new Map<string, RunRecord>();
  for (const r of runs) {
    const cur = latest.get(r.plannedAttemptId);
    if (!cur || r.runNumber > cur.runNumber) latest.set(r.plannedAttemptId, r);
  }
  return new Set([...latest.values()].map((r) => r.id));
}

export class ResultsService {
  constructor(private readonly repos: Repositories) {}

  flatRecords(experimentId?: string, benchmark?: string): FlatRecord[] {
    const all = this.allRecords(experimentId);
    return benchmark ? all.filter((r) => r.task_benchmark === benchmark) : all;
  }

  private allRecords(experimentId?: string): FlatRecord[] {
    const experiments = experimentId ? [this.repos.experiments.get(experimentId)].filter(Boolean) : this.repos.experiments.list();
    const out: FlatRecord[] = [];
    for (const exp of experiments) {
      const runs = this.repos.runs.list({ experimentId: exp!.id });
      const eff = effective(runs);
      for (const r of runs) {
        const task = this.repos.tasks.get(r.taskId);
        const ev: EvaluationRecord | undefined = r.latestEvaluationId ? this.repos.evaluations.get(r.latestEvaluationId) : undefined;
        const meta = (exp!.config.tasks as { id: string; version: string; testVersion: string }[] | undefined)?.find(
          (t) => t.id === r.taskId,
        );
        const isEff = eff.has(r.id);
        out.push({
          experiment_id: exp!.id,
          experiment_name: exp!.name,
          planned_attempt_id: r.plannedAttemptId,
          run_id: r.id,
          run_number: r.runNumber,
          retry_of_run_id: r.retryOfRunId,
          is_effective_run: isEff,
          task_id: r.taskId,
          task_category: task?.category ?? 'unknown',
          task_difficulty: task?.difficulty ?? 'unknown',
          task_kind: task?.kind ?? 'unknown',
          task_benchmark: task ? benchmarkOf(task) : 'unknown',
          task_version: meta?.version ?? task?.version ?? 'unknown',
          test_version: meta?.testVersion ?? task?.testVersion ?? 'unknown',
          task_hash: r.taskHash,
          prompt_hash: r.promptHash,
          assistant_id: r.assistantId,
          assistant_version: r.assistantVersion,
          assistant_version_source: r.assistantVersionSource,
          model: r.model,
          attempt_number: r.attemptNumber,
          execution_mode: r.executionMode,
          eval_mode: r.evalMode,
          operator: r.operator,
          machine_id: r.machineId,
          status: r.status,
          failure_class: r.failureClass,
          outcome: r.outcome,
          success: r.status === 'completed' ? r.success : null,
          evaluation_success: ev?.success ?? null,
          eligible_for_success: isEff && r.status === 'completed',
          timed_out: r.timedOut,
          prepared_at: r.preparedAt,
          started_at: r.startedAt,
          ended_at: r.endedAt,
          submitted_at: r.submittedAt,
          completed_at: r.completedAt,
          wall_clock_seconds: r.wallClockSeconds,
          time_limit_seconds: r.timeLimitSeconds,
          iterations: r.iterations,
          human_interventions: r.humanInterventions,
          acceptance_passed: ev?.acceptancePassed ?? null,
          acceptance_failed: ev?.acceptanceFailed ?? null,
          acceptance_errors: ev?.acceptanceErrors ?? null,
          acceptance_total: ev?.acceptanceTotal ?? null,
          acceptance_expected: ev?.acceptanceExpected ?? null,
          regression_failed: ev?.regressionFailed ?? null,
          regression_errors: ev?.regressionErrors ?? null,
          regression_total: ev?.regressionTotal ?? null,
          regression_failure:
            ev && ev.status === 'completed' && ev.regressionTotal !== null
              ? (ev.regressionFailed ?? 0) + (ev.regressionErrors ?? 0) > 0
              : null,
          line_coverage: ev?.lineCoverage ?? null,
          mutation_score: ev?.mutationScore ?? null,
          ruff_status: ev?.ruffStatus ?? null,
          ruff_count: ev?.ruffCount ?? null,
          ruff_new: ev?.ruffNew ?? null,
          semgrep_status: ev?.semgrepStatus ?? null,
          semgrep_count: ev?.semgrepCount ?? null,
          semgrep_new: ev?.semgrepNew ?? null,
          semgrep_resolved: ev?.semgrepResolved ?? null,
          files_changed: ev?.filesChanged ?? null,
          lines_added: ev?.linesAdded ?? null,
          lines_removed: ev?.linesRemoved ?? null,
          out_of_scope_count: ev?.outOfScopeCount ?? null,
          evaluation_id: ev?.id ?? null,
          evaluator_version: ev?.evaluatorVersion ?? null,
          evaluation_duration_seconds: ev?.durationSeconds ?? null,
          submission_hash: r.submissionHash,
          failure_modes: r.failureModes.join(';'),
          invalidation_reason: r.invalidationReason,
          notes: r.notes,
        });
      }
    }
    return out;
  }

  static aggregate(rows: FlatRecord[], plannedCount: number) {
    const eff = rows.filter((r) => r.is_effective_run);
    const eligible = eff.filter((r) => r.eligible_for_success);
    const successes = eligible.filter((r) => r.success === true).length;
    const nums = (pick: (r: FlatRecord) => number | null) =>
      eligible.map(pick).filter((v): v is number => typeof v === 'number' && Number.isFinite(v));
    const durations = nums((r) => r.wall_clock_seconds);
    const iterations = nums((r) => r.iterations);
    const interventions = nums((r) => r.human_interventions);
    const ruffRan = eligible.filter((r) => r.ruff_status === 'ran');
    const semRan = eligible.filter((r) => r.semgrep_status === 'ran');
    const notStarted = plannedCount - eff.length + eff.filter((r) => r.status === 'planned' || r.status === 'ready').length;
    const ci = wilson(successes, eligible.length);
    const regEligible = eligible.filter((r) => r.regression_failure !== null);
    const coverage = nums((r) => r.line_coverage);
    const mutation = nums((r) => r.mutation_score);
    return {
      planned: plannedCount,
      completed: eligible.length,
      successes,
      successRate: eligible.length ? successes / eligible.length : null,
      successCi95: ci,
      intentToTreatRate: plannedCount ? successes / plannedCount : null,
      notStarted,
      inProgress: eff.filter((r) => ['running', 'awaiting_human', 'submitted', 'evaluating'].includes(r.status)).length,
      operationalFailures: eff.filter((r) => r.status === 'failed').length,
      invalidated: eff.filter((r) => r.status === 'invalidated').length,
      timeouts: eligible.filter((r) => r.timed_out).length,
      retries: rows.filter((r) => r.run_number > 1).length,
      regressionFailures: regEligible.filter((r) => r.regression_failure).length,
      regressionDenominator: regEligible.length,
      duration: {
        n: durations.length,
        mean: mean(durations),
        median: median(durations),
        q1: quantile(durations, 0.25),
        q3: quantile(durations, 0.75),
        min: durations.length ? Math.min(...durations) : null,
        max: durations.length ? Math.max(...durations) : null,
      },
      iterations: { n: iterations.length, mean: mean(iterations), median: median(iterations) },
      interventions: { n: interventions.length, mean: mean(interventions), median: median(interventions) },
      ruff: {
        n: ruffRan.length,
        unavailable: eligible.filter((r) => r.ruff_status && r.ruff_status !== 'ran').length,
        newMean: mean(ruffRan.map((r) => r.ruff_new ?? 0)),
        newTotal: ruffRan.reduce((a, r) => a + (r.ruff_new ?? 0), 0),
      },
      semgrep: {
        n: semRan.length,
        unavailable: eligible.filter((r) => r.semgrep_status && r.semgrep_status !== 'ran').length,
        newTotal: semRan.reduce((a, r) => a + (r.semgrep_new ?? 0), 0),
        runsWithNewFindings: semRan.filter((r) => (r.semgrep_new ?? 0) > 0).length,
        resolvedTotal: semRan.reduce((a, r) => a + (r.semgrep_resolved ?? 0), 0),
      },
      testWriting: { n: coverage.length, meanCoverage: mean(coverage), meanMutationScore: mean(mutation) },
      outOfScopeRuns: eligible.filter((r) => (r.out_of_scope_count ?? 0) > 0).length,
    };
  }

  summary(experimentId?: string, benchmark?: string) {
    const rows = this.flatRecords(experimentId, benchmark);
    const experiments = experimentId ? [this.repos.experiments.get(experimentId)].filter(Boolean) : this.repos.experiments.list();
    const tasks = this.repos.tasks.list().filter((t) => !benchmark || benchmarkOf(t) === benchmark);
    const taskIdSet = new Set(tasks.map((t) => t.id));
    const planned = experiments.flatMap((e) => this.repos.experiments.planned(e!.id)).filter((p) => taskIdSet.has(p.taskId));
    const assistants = this.repos.assistants.list();
    const plannedFor = (pred: (p: (typeof planned)[number]) => boolean) => planned.filter(pred).length;
    const taskCat = new Map(tasks.map((t) => [t.id, t.category]));
    const overall = ResultsService.aggregate(rows, planned.length);
    const byAssistant = assistants.map((a) => ({
      assistantId: a.id,
      name: a.name,
      ...ResultsService.aggregate(
        rows.filter((r) => r.assistant_id === a.id),
        plannedFor((p) => p.assistantId === a.id),
      ),
    }));
    const categories = [...new Set(tasks.map((t) => t.category))];
    const byCategory = categories.map((c) => ({
      category: c,
      ...ResultsService.aggregate(
        rows.filter((r) => r.task_category === c),
        plannedFor((p) => taskCat.get(p.taskId) === c),
      ),
    }));
    const byAssistantCategory = assistants.flatMap((a) =>
      categories.map((c) => ({
        assistantId: a.id,
        category: c,
        exploratory: true,
        ...ResultsService.aggregate(
          rows.filter((r) => r.assistant_id === a.id && r.task_category === c),
          plannedFor((p) => p.assistantId === a.id && taskCat.get(p.taskId) === c),
        ),
      })),
    );
    const evalModes = [...new Set(rows.filter((r) => r.eligible_for_success).map((r) => r.eval_mode))];
    return {
      scope: { ...(experimentId ? { experimentId } : { experimentId: null, experiments: experiments.length }), benchmark: benchmark ?? null },
      hasData: overall.completed > 0,
      generatedAt: new Date().toISOString(),
      totals: {
        tasks: tasks.length,
        validatedTasks: tasks.filter((t) => t.validationStatus === 'validated').length,
        assistants: assistants.length,
        experiments: experiments.length,
        plannedAttempts: planned.length,
        runsRecorded: rows.length,
      },
      overall,
      byAssistant,
      byCategory,
      byAssistantCategory,
      caveats: [
        'Success rate = successful completed effective runs / completed effective runs. Runs that never completed evaluation are excluded and reported separately.',
        ...(benchmark === 'swebench_verified'
          ? ['SWE-bench success = resolved by the official harness: every FAIL_TO_PASS and PASS_TO_PASS test passes. The 12-task sample is a pilot; report exact counts.']
          : benchmark === 'golden_verified'
            ? ['Golden success = resolved by the official SWE-bench harness. Categories are golden-dataset domains; non-bug-fix domains have few tasks, so report exact counts.']
            : ['Category-level results are exploratory: each category has only three tasks.']),
        ...(!benchmark && new Set(rows.map((r) => r.task_benchmark)).size > 1
          ? ['These figures pool several benchmarks. Filter by benchmark before comparing.']
          : []),
        'Confidence intervals are Wilson 95% intervals for a binomial proportion and assume independent attempts; repeated attempts on the same task are not independent.',
        ...(evalModes.length > 1 ? [`Results mix evaluation modes (${evalModes.join(', ')}); compare with care.`] : []),
      ],
    };
  }
}
