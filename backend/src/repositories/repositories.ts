/**
 * Data-access layer. Every SQL statement used by the application lives in this file so that the
 * storage engine can be swapped (see docs/architecture.md) without touching the services.
 */
import { randomUUID } from 'node:crypto';
import { type Database, nowIso, type Row } from '../db/database.ts';
import type { AssistantRecord, EvaluationRecord, EventRecord, ExperimentRecord, PlannedAttempt, RunRecord, TaskRecord } from '../types.ts';
import { toAssistant, toEvaluation, toEvent, toExperiment, toPlanned, toRun, toTask } from './mappers.ts';

// ----------------------------------------------------------------------------------------- tasks

export class TaskRepository {
  constructor(private readonly db: Database) {}

  list(): TaskRecord[] {
    return this.db.all('SELECT * FROM tasks ORDER BY id').map(toTask);
  }

  get(id: string): TaskRecord | undefined {
    const row = this.db.get('SELECT * FROM tasks WHERE id = ?', id);
    return row ? toTask(row) : undefined;
  }

  upsert(t: Omit<TaskRecord, 'syncedAt'>): void {
    const now = nowIso();
    this.db.run(
      `INSERT INTO tasks (id, title, category, difficulty, kind, version, test_version, task_hash, prompt_hash, test_hash,
         starter_hash, validation_status, validated_at, expected_acceptance_total, prompt, metadata_json, synced_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET title=excluded.title, category=excluded.category, difficulty=excluded.difficulty,
         kind=excluded.kind, version=excluded.version, test_version=excluded.test_version, task_hash=excluded.task_hash,
         prompt_hash=excluded.prompt_hash, test_hash=excluded.test_hash, starter_hash=excluded.starter_hash,
         validation_status=excluded.validation_status, validated_at=excluded.validated_at,
         expected_acceptance_total=excluded.expected_acceptance_total, prompt=excluded.prompt,
         metadata_json=excluded.metadata_json, synced_at=excluded.synced_at`,
      t.id,
      t.title,
      t.category,
      t.difficulty,
      t.kind,
      t.version,
      t.testVersion,
      t.taskHash,
      t.promptHash,
      t.testHash,
      t.starterHash,
      t.validationStatus,
      t.validatedAt,
      t.expectedAcceptanceTotal,
      t.prompt,
      JSON.stringify(t.metadata),
      now,
    );
    this.db.run(
      `INSERT OR IGNORE INTO task_versions (task_id, task_hash, version, test_version, prompt_hash, test_hash, prompt,
         metadata_json, first_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      t.id,
      t.taskHash,
      t.version,
      t.testVersion,
      t.promptHash,
      t.testHash,
      t.prompt,
      JSON.stringify(t.metadata),
      now,
    );
  }

  versions(taskId: string): Row[] {
    return this.db.all(
      'SELECT task_hash, version, test_version, prompt_hash, test_hash, first_seen_at FROM task_versions WHERE task_id = ? ORDER BY first_seen_at',
      taskId,
    );
  }

  versionPrompt(taskId: string, taskHash: string): string | undefined {
    return this.db.get<{ prompt: string }>('SELECT prompt FROM task_versions WHERE task_id = ? AND task_hash = ?', taskId, taskHash)
      ?.prompt;
  }
}

// ------------------------------------------------------------------------------------ assistants

export class AssistantRepository {
  constructor(private readonly db: Database) {}

  list(): AssistantRecord[] {
    return this.db
      .all(`SELECT * FROM assistants ORDER BY CASE id WHEN 'copilot' THEN 1 WHEN 'cursor' THEN 2 WHEN 'claude_code' THEN 3 ELSE 4 END`)
      .map(toAssistant);
  }

  get(id: string): AssistantRecord | undefined {
    const row = this.db.get('SELECT * FROM assistants WHERE id = ?', id);
    return row ? toAssistant(row) : undefined;
  }

  ensure(a: Pick<AssistantRecord, 'id' | 'name' | 'vendor' | 'interface'>): void {
    this.db.run(
      `INSERT INTO assistants (id, name, vendor, interface, capability_status) VALUES (?, ?, ?, ?, 'not_configured')
       ON CONFLICT(id) DO UPDATE SET name=excluded.name, vendor=excluded.vendor, interface=excluded.interface`,
      a.id,
      a.name,
      a.vendor,
      a.interface,
    );
  }

  setCapability(id: string, status: string, detail: string | null, detectedVersion: string | null): void {
    this.db.run(
      'UPDATE assistants SET capability_status = ?, capability_detail = ?, detected_version = ?, checked_at = ? WHERE id = ?',
      status,
      detail,
      detectedVersion,
      nowIso(),
      id,
    );
  }

  setOperatorReported(id: string, version: string | null, model: string | null): void {
    this.db.run('UPDATE assistants SET operator_reported_version = ?, operator_reported_model = ? WHERE id = ?', version, model, id);
  }
}

// ----------------------------------------------------------------------------------- experiments

export interface NewExperiment {
  id: string;
  name: string;
  description: string;
  executionMode: 'human' | 'automated';
  evalMode: 'docker' | 'local';
  attemptsPerPair: number;
  timeLimitOverrideMinutes: number | null;
  randomizeOrder: boolean;
  seed: number;
  config: Record<string, unknown>;
  createdBy: string;
  machineId: string;
}

export class ExperimentRepository {
  constructor(private readonly db: Database) {}

  list(): ExperimentRecord[] {
    return this.db.all('SELECT * FROM experiments ORDER BY created_at DESC').map(toExperiment);
  }

  get(id: string): ExperimentRecord | undefined {
    const row = this.db.get('SELECT * FROM experiments WHERE id = ?', id);
    return row ? toExperiment(row) : undefined;
  }

  insert(e: NewExperiment, createdAt = nowIso()): void {
    this.db.run(
      `INSERT INTO experiments (id, name, description, status, execution_mode, eval_mode, attempts_per_pair,
         time_limit_override_minutes, randomize_order, seed, config_json, created_by, machine_id, created_at)
       VALUES (?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      e.id,
      e.name,
      e.description,
      e.executionMode,
      e.evalMode,
      e.attemptsPerPair,
      e.timeLimitOverrideMinutes,
      e.randomizeOrder ? 1 : 0,
      e.seed,
      JSON.stringify(e.config),
      e.createdBy,
      e.machineId,
      createdAt,
    );
  }

  insertRaw(row: Row): void {
    const cols = Object.keys(row);
    this.db.run(
      `INSERT INTO experiments (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`,
      ...(cols.map((c) => row[c]) as (string | number | null)[]),
    );
  }

  setStatus(id: string, status: ExperimentRecord['status'], field?: 'started_at' | 'completed_at'): void {
    if (field) this.db.run(`UPDATE experiments SET status = ?, ${field} = ? WHERE id = ?`, status, nowIso(), id);
    else this.db.run('UPDATE experiments SET status = ? WHERE id = ?', status, id);
  }

  insertPlanned(p: PlannedAttempt): void {
    this.db.run(
      `INSERT INTO planned_attempts (id, experiment_id, task_id, task_hash, prompt_hash, assistant_id, attempt_number,
         sequence, time_limit_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      p.id,
      p.experimentId,
      p.taskId,
      p.taskHash,
      p.promptHash,
      p.assistantId,
      p.attemptNumber,
      p.sequence,
      p.timeLimitSeconds,
    );
  }

  planned(experimentId: string): PlannedAttempt[] {
    return this.db.all('SELECT * FROM planned_attempts WHERE experiment_id = ? ORDER BY sequence', experimentId).map(toPlanned);
  }

  plannedById(id: string): PlannedAttempt | undefined {
    const row = this.db.get('SELECT * FROM planned_attempts WHERE id = ?', id);
    return row ? toPlanned(row) : undefined;
  }

  rawRows(table: 'experiments' | 'planned_attempts', experimentId: string): Row[] {
    const column = table === 'experiments' ? 'id' : 'experiment_id';
    return this.db.all(`SELECT * FROM ${table} WHERE ${column} = ?`, experimentId);
  }
}

// ------------------------------------------------------------------------------------------ runs

export interface RunFilter {
  experimentId?: string;
  status?: string;
  assistantId?: string;
  taskId?: string;
  limit?: number;
}

const RUN_COLUMNS: Record<string, string> = {
  status: 'status',
  executionMode: 'execution_mode',
  workspacePath: 'workspace_path',
  assistantVersion: 'assistant_version',
  assistantVersionSource: 'assistant_version_source',
  model: 'model',
  preparedAt: 'prepared_at',
  startedAt: 'started_at',
  endedAt: 'ended_at',
  submittedAt: 'submitted_at',
  completedAt: 'completed_at',
  wallClockSeconds: 'wall_clock_seconds',
  timedOut: 'timed_out',
  iterations: 'iterations',
  humanInterventions: 'human_interventions',
  notes: 'notes',
  submissionKind: 'submission_kind',
  submissionHash: 'submission_hash',
  failureClass: 'failure_class',
  errorMessage: 'error_message',
  failureModes: 'failure_modes_json',
  invalidationReason: 'invalidation_reason',
  success: 'success',
  outcome: 'outcome',
  latestEvaluationId: 'latest_evaluation_id',
};

export class RunRepository {
  constructor(private readonly db: Database) {}

  insert(r: Omit<RunRecord, 'createdAt' | 'updatedAt'>): void {
    const now = nowIso();
    this.db.run(
      `INSERT INTO runs (id, planned_attempt_id, experiment_id, task_id, assistant_id, attempt_number, run_number,
         retry_of_run_id, status, execution_mode, eval_mode, task_hash, prompt_hash, operator, machine_id,
         time_limit_seconds, notes, failure_modes_json, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      r.id,
      r.plannedAttemptId,
      r.experimentId,
      r.taskId,
      r.assistantId,
      r.attemptNumber,
      r.runNumber,
      r.retryOfRunId,
      r.status,
      r.executionMode,
      r.evalMode,
      r.taskHash,
      r.promptHash,
      r.operator,
      r.machineId,
      r.timeLimitSeconds,
      r.notes,
      JSON.stringify(r.failureModes),
      now,
      now,
    );
  }

  insertRaw(row: Row): void {
    const cols = Object.keys(row);
    this.db.run(
      `INSERT INTO runs (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`,
      ...(cols.map((c) => row[c]) as (string | number | null)[]),
    );
  }

  get(id: string): RunRecord | undefined {
    const row = this.db.get('SELECT * FROM runs WHERE id = ?', id);
    return row ? toRun(row) : undefined;
  }

  rawRow(id: string): Row | undefined {
    return this.db.get('SELECT * FROM runs WHERE id = ?', id);
  }

  list(filter: RunFilter = {}): RunRecord[] {
    const where: string[] = [];
    const params: (string | number)[] = [];
    if (filter.experimentId) {
      where.push('experiment_id = ?');
      params.push(filter.experimentId);
    }
    if (filter.status) {
      where.push('status = ?');
      params.push(filter.status);
    }
    if (filter.assistantId) {
      where.push('assistant_id = ?');
      params.push(filter.assistantId);
    }
    if (filter.taskId) {
      where.push('task_id = ?');
      params.push(filter.taskId);
    }
    const sql = `SELECT * FROM runs ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
      ORDER BY experiment_id, (SELECT sequence FROM planned_attempts p WHERE p.id = runs.planned_attempt_id), run_number
      ${filter.limit ? `LIMIT ${Math.min(Math.max(filter.limit, 1), 5000)}` : ''}`;
    return this.db.all(sql, ...params).map(toRun);
  }

  forAttempt(plannedAttemptId: string): RunRecord[] {
    return this.db.all('SELECT * FROM runs WHERE planned_attempt_id = ? ORDER BY run_number', plannedAttemptId).map(toRun);
  }

  byStatus(statuses: string[]): RunRecord[] {
    return this.db.all(`SELECT * FROM runs WHERE status IN (${statuses.map(() => '?').join(',')})`, ...statuses).map(toRun);
  }

  update(id: string, patch: Partial<RunRecord>): void {
    const sets: string[] = [];
    const params: (string | number | null)[] = [];
    for (const [key, value] of Object.entries(patch)) {
      const column = RUN_COLUMNS[key];
      if (!column) throw new Error(`run field not updatable: ${key}`);
      sets.push(`${column} = ?`);
      if (key === 'failureModes') params.push(JSON.stringify(value));
      else if (typeof value === 'boolean') params.push(value ? 1 : 0);
      else params.push((value ?? null) as string | number | null);
    }
    if (!sets.length) return;
    sets.push('updated_at = ?');
    params.push(nowIso(), id);
    this.db.run(`UPDATE runs SET ${sets.join(', ')} WHERE id = ?`, ...params);
  }
}

// ----------------------------------------------------------------------------------- evaluations

export class EvaluationRepository {
  constructor(private readonly db: Database) {}

  create(runId: string, evalMode: string): EvaluationRecord {
    const id = randomUUID();
    this.db.run(
      `INSERT INTO evaluations (id, run_id, status, eval_mode, queued_at) VALUES (?, ?, 'queued', ?, ?)`,
      id,
      runId,
      evalMode,
      nowIso(),
    );
    return this.get(id)!;
  }

  get(id: string): EvaluationRecord | undefined {
    const row = this.db.get('SELECT * FROM evaluations WHERE id = ?', id);
    return row ? toEvaluation(row) : undefined;
  }

  forRun(runId: string): EvaluationRecord[] {
    return this.db.all('SELECT * FROM evaluations WHERE run_id = ? ORDER BY queued_at', runId).map(toEvaluation);
  }

  byStatus(statuses: string[]): EvaluationRecord[] {
    return this.db.all(`SELECT * FROM evaluations WHERE status IN (${statuses.map(() => '?').join(',')})`, ...statuses).map(toEvaluation);
  }

  markRunning(id: string, artifactDir: string): void {
    this.db.run(`UPDATE evaluations SET status = 'running', started_at = ?, artifact_dir = ? WHERE id = ?`, nowIso(), artifactDir, id);
  }

  finish(id: string, fields: Record<string, string | number | null>): void {
    const cols = Object.keys(fields);
    this.db.run(
      `UPDATE evaluations SET ${cols.map((c) => `${c} = ?`).join(', ')}, finished_at = ? WHERE id = ?`,
      ...cols.map((c) => fields[c]),
      nowIso(),
      id,
    );
  }

  addTestOutcome(
    evaluationId: string,
    suite: string,
    testId: string,
    outcome: string,
    duration: number | null,
    message: string | null,
  ): void {
    this.db.run(
      'INSERT INTO test_outcomes (evaluation_id, suite, test_id, outcome, duration_seconds, message) VALUES (?, ?, ?, ?, ?, ?)',
      evaluationId,
      suite,
      testId,
      outcome,
      duration,
      message,
    );
  }

  testOutcomes(evaluationId: string): Row[] {
    return this.db.all(
      'SELECT suite, test_id, outcome, duration_seconds, message FROM test_outcomes WHERE evaluation_id = ? ORDER BY suite, id',
      evaluationId,
    );
  }

  addFinding(
    evaluationId: string,
    f: {
      tool: string;
      ruleId: string;
      severity: string | null;
      path: string | null;
      line: number | null;
      message: string | null;
      isNew: boolean;
    },
  ): void {
    this.db.run(
      'INSERT INTO findings (evaluation_id, tool, rule_id, severity, path, line, message, is_new) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      evaluationId,
      f.tool,
      f.ruleId,
      f.severity,
      f.path,
      f.line,
      f.message,
      f.isNew ? 1 : 0,
    );
  }

  findings(evaluationId: string): Row[] {
    return this.db.all(
      'SELECT tool, rule_id, severity, path, line, message, is_new FROM findings WHERE evaluation_id = ? ORDER BY tool, is_new DESC, path, line',
      evaluationId,
    );
  }

  rawRowsForRuns(runIds: string[], table: 'evaluations' | 'test_outcomes' | 'findings'): Row[] {
    if (!runIds.length) return [];
    const marks = runIds.map(() => '?').join(',');
    if (table === 'evaluations') return this.db.all(`SELECT * FROM evaluations WHERE run_id IN (${marks})`, ...runIds);
    return this.db.all(`SELECT t.* FROM ${table} t JOIN evaluations e ON e.id = t.evaluation_id WHERE e.run_id IN (${marks})`, ...runIds);
  }

  insertRaw(table: 'evaluations' | 'test_outcomes' | 'findings', row: Row): void {
    const cols = Object.keys(row).filter((c) => !(table !== 'evaluations' && c === 'id'));
    this.db.run(
      `INSERT INTO ${table} (${cols.join(',')}) VALUES (${cols.map(() => '?').join(',')})`,
      ...(cols.map((c) => row[c]) as (string | number | null)[]),
    );
  }
}

// ------------------------------------------------------------------------------------- artifacts

export interface ArtifactRow {
  id: string;
  runId: string;
  evaluationId: string | null;
  kind: string;
  relativePath: string;
  sizeBytes: number;
  sha256: string;
  createdAt: string;
}

export class ArtifactRepository {
  constructor(private readonly db: Database) {}

  add(a: Omit<ArtifactRow, 'id' | 'createdAt'>): ArtifactRow {
    const row = { ...a, id: randomUUID(), createdAt: nowIso() };
    this.db.run(
      'INSERT INTO artifacts (id, run_id, evaluation_id, kind, relative_path, size_bytes, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      row.id,
      row.runId,
      row.evaluationId,
      row.kind,
      row.relativePath,
      row.sizeBytes,
      row.sha256,
      row.createdAt,
    );
    return row;
  }

  forRun(runId: string): ArtifactRow[] {
    return this.db.all('SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at, relative_path', runId).map((r) => ({
      id: String(r.id),
      runId: String(r.run_id),
      evaluationId: r.evaluation_id ? String(r.evaluation_id) : null,
      kind: String(r.kind),
      relativePath: String(r.relative_path),
      sizeBytes: Number(r.size_bytes),
      sha256: String(r.sha256),
      createdAt: String(r.created_at),
    }));
  }

  get(id: string): ArtifactRow | undefined {
    return this.forRunById(id);
  }

  private forRunById(id: string): ArtifactRow | undefined {
    const r = this.db.get('SELECT * FROM artifacts WHERE id = ?', id);
    if (!r) return undefined;
    return {
      id: String(r.id),
      runId: String(r.run_id),
      evaluationId: r.evaluation_id ? String(r.evaluation_id) : null,
      kind: String(r.kind),
      relativePath: String(r.relative_path),
      sizeBytes: Number(r.size_bytes),
      sha256: String(r.sha256),
      createdAt: String(r.created_at),
    };
  }
}

// ---------------------------------------------------------------------------------------- events

export class EventRepository {
  constructor(private readonly db: Database) {}

  add(e: {
    runId?: string | null;
    experimentId?: string | null;
    type: string;
    fromStatus?: string | null;
    toStatus?: string | null;
    actor: string;
    payload?: Record<string, unknown>;
  }): void {
    this.db.run(
      'INSERT INTO events (run_id, experiment_id, type, from_status, to_status, actor, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      e.runId ?? null,
      e.experimentId ?? null,
      e.type,
      e.fromStatus ?? null,
      e.toStatus ?? null,
      e.actor,
      JSON.stringify(e.payload ?? {}),
      nowIso(),
    );
  }

  forRun(runId: string): EventRecord[] {
    return this.db.all('SELECT * FROM events WHERE run_id = ? ORDER BY id', runId).map(toEvent);
  }

  recent(limit = 20): EventRecord[] {
    return this.db.all('SELECT * FROM events ORDER BY id DESC LIMIT ?', Math.min(Math.max(limit, 1), 200)).map(toEvent);
  }

  rawForExperiment(experimentId: string): Row[] {
    return this.db.all(
      'SELECT * FROM events WHERE experiment_id = ? OR run_id IN (SELECT id FROM runs WHERE experiment_id = ?) ORDER BY id',
      experimentId,
      experimentId,
    );
  }
}

export interface Repositories {
  tasks: TaskRepository;
  assistants: AssistantRepository;
  experiments: ExperimentRepository;
  runs: RunRepository;
  evaluations: EvaluationRepository;
  artifacts: ArtifactRepository;
  events: EventRepository;
}

export function createRepositories(db: Database): Repositories {
  return {
    tasks: new TaskRepository(db),
    assistants: new AssistantRepository(db),
    experiments: new ExperimentRepository(db),
    runs: new RunRepository(db),
    evaluations: new EvaluationRepository(db),
    artifacts: new ArtifactRepository(db),
    events: new EventRepository(db),
  };
}
