export type RunStatus =
  | 'planned'
  | 'ready'
  | 'running'
  | 'awaiting_human'
  | 'submitted'
  | 'evaluating'
  | 'completed'
  | 'failed'
  | 'invalidated';

export interface Task {
  id: string;
  title: string;
  category: string;
  difficulty: string;
  kind: string;
  version: string;
  testVersion: string;
  taskHash: string;
  promptHash: string;
  testHash: string;
  starterHash: string;
  validationStatus: string;
  validatedAt: string | null;
  expectedAcceptanceTotal: number | null;
  prompt?: string;
  metadata: {
    summary: string;
    difficultyRationale: string;
    requiredBehavior: string[];
    acceptanceCriteria: string[];
    acceptanceTests: { id: string; description: string }[];
    scope: { allowed_paths: string[]; protected_paths: string[] };
    timeLimitMinutes: number;
    testTimeoutSeconds: number;
    testWriting: Record<string, unknown> | null;
    directory: string;
    starterLocation: string;
    starterFiles: { path: string; size: number }[];
    benchmark?: string;
    swebench?: SwebenchMeta | null;
  };
}

/** Extra metadata for SWE-bench Verified tasks (real GitHub issues). */
export interface SwebenchMeta {
  dataset: string;
  repo: string;
  base_commit: string | null;
  tier: string;
  leaderboard_share: number | null;
  leaderboard_solved_by: number | null;
  dataset_difficulty: string | null;
  fail_to_pass_count: number | null;
  pass_to_pass_count: number | null;
  has_dataset: boolean;
  /** Golden-dataset labels, present when the instance is in the golden set. */
  golden?: GoldenLabels | null;
}

export interface GoldenLabels {
  golden_task_id: string;
  domain: string;
  subdomain: string | null;
  domain_confidence: number | null;
  tier: string;
  gold_quality_score: number | null;
  gate_flags: string[];
}

export interface Assistant {
  id: string;
  name: string;
  vendor: string;
  interface: string;
  capabilityStatus: string;
  capabilityDetail: string | null;
  detectedVersion: string | null;
  operatorReportedVersion: string | null;
  operatorReportedModel: string | null;
  checkedAt: string | null;
  manualInstructions?: string;
  docsUrl?: string;
}

export interface Progress {
  planned: number;
  totalRuns: number;
  retries: number;
  byStatus: Record<string, number>;
  completed: number;
  started: number;
}

export interface Experiment {
  id: string;
  name: string;
  description: string;
  status: 'planned' | 'active' | 'completed' | 'archived';
  executionMode: 'human' | 'automated';
  evalMode: 'docker' | 'local';
  attemptsPerPair: number;
  timeLimitOverrideMinutes: number | null;
  randomizeOrder: boolean;
  seed: number;
  config: Record<string, any>;
  createdBy: string;
  machineId: string;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  progress?: Progress;
}

export interface PlannedAttempt {
  id: string;
  taskId: string;
  assistantId: string;
  attemptNumber: number;
  sequence: number;
  timeLimitSeconds: number;
}

export interface Run {
  id: string;
  plannedAttemptId: string;
  experimentId: string;
  taskId: string;
  assistantId: string;
  attemptNumber: number;
  runNumber: number;
  retryOfRunId: string | null;
  status: RunStatus;
  executionMode: string;
  evalMode: string;
  taskHash: string;
  promptHash: string;
  workspacePath: string | null;
  assistantVersion: string | null;
  assistantVersionSource: string;
  model: string | null;
  operator: string;
  machineId: string;
  timeLimitSeconds: number;
  preparedAt: string | null;
  startedAt: string | null;
  endedAt: string | null;
  submittedAt: string | null;
  completedAt: string | null;
  wallClockSeconds: number | null;
  timedOut: boolean;
  iterations: number | null;
  humanInterventions: number | null;
  notes: string;
  submissionKind: string | null;
  submissionHash: string | null;
  failureClass: string | null;
  errorMessage: string | null;
  failureModes: string[];
  invalidationReason: string | null;
  success: boolean | null;
  outcome: string | null;
  latestEvaluationId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Evaluation {
  id: string;
  status: string;
  evalMode: string;
  evaluatorVersion: string | null;
  success: boolean | null;
  outcome: string | null;
  errorClass: string | null;
  errorMessage: string | null;
  acceptancePassed: number | null;
  acceptanceFailed: number | null;
  acceptanceErrors: number | null;
  acceptanceTotal: number | null;
  acceptanceExpected: number | null;
  regressionPassed: number | null;
  regressionFailed: number | null;
  regressionErrors: number | null;
  regressionTotal: number | null;
  ruffStatus: string | null;
  ruffCount: number | null;
  ruffNew: number | null;
  semgrepStatus: string | null;
  semgrepCount: number | null;
  semgrepNew: number | null;
  semgrepResolved: number | null;
  lineCoverage: number | null;
  mutationScore: number | null;
  filesChanged: number | null;
  linesAdded: number | null;
  linesRemoved: number | null;
  outOfScopeCount: number | null;
  durationSeconds: number | null;
  toolVersions: Record<string, any>;
  queuedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface RunDetail {
  run: Run;
  task: { id: string; title: string; category: string; difficulty: string; version: string; kind: string } | null;
  prompt: string;
  promptHash: string;
  assistant: Assistant;
  evaluations: Evaluation[];
  latestEvaluation: Evaluation | null;
  testOutcomes: { suite: string; test_id: string; outcome: string; duration_seconds: number | null; message: string | null }[];
  findings: {
    tool: string;
    rule_id: string;
    severity: string | null;
    path: string | null;
    line: number | null;
    message: string | null;
    is_new: number;
  }[];
  artifacts: { id: string; kind: string; relativePath: string; sizeBytes: number; sha256: string; createdAt: string }[];
  events: {
    id: number;
    type: string;
    fromStatus: string | null;
    toStatus: string | null;
    actor: string;
    payload: Record<string, unknown>;
    createdAt: string;
  }[];
  siblings: { id: string; runNumber: number; status: RunStatus }[];
}

export interface Aggregate {
  planned: number;
  completed: number;
  successes: number;
  successRate: number | null;
  successCi95: { low: number; high: number } | null;
  intentToTreatRate: number | null;
  notStarted: number;
  inProgress: number;
  operationalFailures: number;
  invalidated: number;
  timeouts: number;
  retries: number;
  regressionFailures: number;
  regressionDenominator: number;
  duration: {
    n: number;
    mean: number | null;
    median: number | null;
    q1: number | null;
    q3: number | null;
    min: number | null;
    max: number | null;
  };
  iterations: { n: number; mean: number | null; median: number | null };
  interventions: { n: number; mean: number | null; median: number | null };
  ruff: { n: number; unavailable: number; newMean: number | null; newTotal: number };
  semgrep: { n: number; unavailable: number; newTotal: number; runsWithNewFindings: number; resolvedTotal: number };
  testWriting: { n: number; meanCoverage: number | null; meanMutationScore: number | null };
  outOfScopeRuns: number;
}

export interface Summary {
  scope: { experimentId: string | null; experiments?: number; benchmark?: string | null };
  hasData: boolean;
  generatedAt: string;
  totals: { tasks: number; validatedTasks: number; assistants: number; experiments: number; plannedAttempts: number; runsRecorded: number };
  overall: Aggregate;
  byAssistant: (Aggregate & { assistantId: string; name: string })[];
  byCategory: (Aggregate & { category: string })[];
  byAssistantCategory: (Aggregate & { assistantId: string; category: string; exploratory: boolean })[];
  caveats: string[];
}

export interface EventItem {
  id: number;
  runId: string | null;
  experimentId: string | null;
  type: string;
  fromStatus: string | null;
  toStatus: string | null;
  actor: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

export interface EvidenceSource {
  id: string;
  title: string;
  authors: string[];
  year: number;
  venue: string;
  url: string;
  arxiv?: string;
  doi?: string;
  role: string;
  verified: string[];
  cautions: string[];
}
export interface EvidenceItem {
  id: string;
  theme: string;
  source: string;
  subject: string;
  metric: string;
  value: number | null;
  unit: string;
  n?: number;
  conditions: string;
}
export interface AssistantFeatures {
  id: string;
  name: string;
  vendor: string;
  interactionModes: string[];
  autonomy: string[];
  context: string;
  tooling: string;
  execution: string;
  deployment: string;
  prOutput: string;
  sources: string[];
  note?: string;
}
export interface EvidenceRegistry {
  checkedOn: string;
  themes: Record<string, string>;
  sources: EvidenceSource[];
  items: EvidenceItem[];
  features: { checkedOn: string; autonomyScale: Record<string, string>; assistants: AssistantFeatures[] };
}
