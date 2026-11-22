/**
 * Ordered, append-only schema migrations. Never edit a released migration; add a new one.
 * See docs/architecture.md ("Database and migrations") for the migration path to PostgreSQL.
 */
export interface Migration {
  version: number;
  name: string;
  sql: string;
}

export const RUN_STATUSES = [
  'planned',
  'ready',
  'running',
  'awaiting_human',
  'submitted',
  'evaluating',
  'completed',
  'failed',
  'invalidated',
] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export const FAILURE_CLASSES = [
  'task_failure',
  'timeout',
  'evaluator_error',
  'adapter_error',
  'environment_error',
  'operator_abort',
  'invalid',
] as const;
export type FailureClass = (typeof FAILURE_CLASSES)[number];

const statusList = RUN_STATUSES.map((s) => `'${s}'`).join(',');
const failureList = FAILURE_CLASSES.map((s) => `'${s}'`).join(',');

export const MIGRATIONS: Migration[] = [
  {
    version: 1,
    name: 'initial schema',
    sql: `
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  kind TEXT NOT NULL,
  version TEXT NOT NULL,
  test_version TEXT NOT NULL,
  task_hash TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  test_hash TEXT NOT NULL,
  starter_hash TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  validated_at TEXT,
  expected_acceptance_total INTEGER,
  prompt TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  synced_at TEXT NOT NULL
);

CREATE TABLE task_versions (
  task_id TEXT NOT NULL REFERENCES tasks(id),
  task_hash TEXT NOT NULL,
  version TEXT NOT NULL,
  test_version TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  test_hash TEXT NOT NULL,
  prompt TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  PRIMARY KEY (task_id, task_hash)
);

CREATE TABLE assistants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  vendor TEXT NOT NULL,
  interface TEXT NOT NULL,
  capability_status TEXT NOT NULL CHECK (capability_status IN
    ('supported','requires_authentication','requires_manual_execution','not_configured','unsupported')),
  capability_detail TEXT,
  detected_version TEXT,
  operator_reported_version TEXT,
  operator_reported_model TEXT,
  checked_at TEXT,
  config_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE experiments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('planned','active','completed','archived')),
  execution_mode TEXT NOT NULL CHECK (execution_mode IN ('human','automated')),
  eval_mode TEXT NOT NULL CHECK (eval_mode IN ('docker','local')),
  attempts_per_pair INTEGER NOT NULL CHECK (attempts_per_pair BETWEEN 1 AND 10),
  time_limit_override_minutes INTEGER,
  randomize_order INTEGER NOT NULL DEFAULT 1,
  seed INTEGER NOT NULL,
  config_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT
);

CREATE TABLE planned_attempts (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL REFERENCES experiments(id),
  task_id TEXT NOT NULL REFERENCES tasks(id),
  task_hash TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  assistant_id TEXT NOT NULL REFERENCES assistants(id),
  attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
  sequence INTEGER NOT NULL,
  time_limit_seconds INTEGER NOT NULL,
  UNIQUE (experiment_id, task_id, assistant_id, attempt_number)
);
CREATE INDEX idx_planned_experiment ON planned_attempts(experiment_id, sequence);

CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  planned_attempt_id TEXT NOT NULL REFERENCES planned_attempts(id),
  experiment_id TEXT NOT NULL REFERENCES experiments(id),
  task_id TEXT NOT NULL REFERENCES tasks(id),
  assistant_id TEXT NOT NULL REFERENCES assistants(id),
  attempt_number INTEGER NOT NULL,
  run_number INTEGER NOT NULL DEFAULT 1,
  retry_of_run_id TEXT REFERENCES runs(id),
  status TEXT NOT NULL CHECK (status IN (${statusList})),
  execution_mode TEXT NOT NULL,
  eval_mode TEXT NOT NULL,
  task_hash TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  workspace_path TEXT,
  assistant_version TEXT,
  assistant_version_source TEXT NOT NULL DEFAULT 'unknown',
  model TEXT,
  operator TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  time_limit_seconds INTEGER NOT NULL,
  prepared_at TEXT,
  started_at TEXT,
  ended_at TEXT,
  submitted_at TEXT,
  completed_at TEXT,
  wall_clock_seconds REAL,
  timed_out INTEGER NOT NULL DEFAULT 0,
  iterations INTEGER,
  human_interventions INTEGER,
  notes TEXT NOT NULL DEFAULT '',
  submission_kind TEXT,
  submission_hash TEXT,
  failure_class TEXT CHECK (failure_class IS NULL OR failure_class IN (${failureList})),
  error_message TEXT,
  failure_modes_json TEXT NOT NULL DEFAULT '[]',
  invalidation_reason TEXT,
  success INTEGER,
  outcome TEXT,
  latest_evaluation_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (planned_attempt_id, run_number)
);
CREATE INDEX idx_runs_experiment ON runs(experiment_id, status);
CREATE INDEX idx_runs_attempt ON runs(planned_attempt_id);

CREATE TABLE evaluations (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  status TEXT NOT NULL CHECK (status IN ('queued','running','completed','error')),
  eval_mode TEXT NOT NULL,
  evaluator_version TEXT,
  success INTEGER,
  outcome TEXT,
  error_class TEXT,
  error_message TEXT,
  acceptance_passed INTEGER,
  acceptance_failed INTEGER,
  acceptance_errors INTEGER,
  acceptance_total INTEGER,
  acceptance_expected INTEGER,
  regression_passed INTEGER,
  regression_failed INTEGER,
  regression_errors INTEGER,
  regression_total INTEGER,
  ruff_status TEXT,
  ruff_count INTEGER,
  ruff_new INTEGER,
  semgrep_status TEXT,
  semgrep_count INTEGER,
  semgrep_new INTEGER,
  semgrep_resolved INTEGER,
  line_coverage REAL,
  mutation_score REAL,
  files_changed INTEGER,
  lines_added INTEGER,
  lines_removed INTEGER,
  out_of_scope_count INTEGER,
  duration_seconds REAL,
  artifact_dir TEXT,
  tool_versions_json TEXT NOT NULL DEFAULT '{}',
  queued_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT
);
CREATE INDEX idx_evaluations_run ON evaluations(run_id);

CREATE TABLE test_outcomes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL REFERENCES evaluations(id),
  suite TEXT NOT NULL CHECK (suite IN ('acceptance','regression','quality')),
  test_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  duration_seconds REAL,
  message TEXT
);
CREATE INDEX idx_test_outcomes_eval ON test_outcomes(evaluation_id);

CREATE TABLE findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL REFERENCES evaluations(id),
  tool TEXT NOT NULL CHECK (tool IN ('ruff','semgrep')),
  rule_id TEXT NOT NULL,
  severity TEXT,
  path TEXT,
  line INTEGER,
  message TEXT,
  is_new INTEGER NOT NULL
);
CREATE INDEX idx_findings_eval ON findings(evaluation_id);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  evaluation_id TEXT REFERENCES evaluations(id),
  kind TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_artifacts_run ON artifacts(run_id);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT REFERENCES runs(id),
  experiment_id TEXT REFERENCES experiments(id),
  type TEXT NOT NULL,
  from_status TEXT,
  to_status TEXT,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX idx_events_run ON events(run_id);
CREATE INDEX idx_events_time ON events(created_at);
`,
  },
  {
    version: 2,
    name: 'patch code quality',
    // Code quality of the assistant's patch on SWE-bench / golden tasks (evaluator/patch_quality.py):
    // the golden Code Quality Module's score, its per-dimension sub-scores, and the reference fix's score.
    sql: `
ALTER TABLE evaluations ADD COLUMN quality_status TEXT;
ALTER TABLE evaluations ADD COLUMN quality_score REAL;
ALTER TABLE evaluations ADD COLUMN quality_gold_score REAL;
ALTER TABLE evaluations ADD COLUMN quality_json TEXT;
`,
  },
];
