import type { FailureClass, RunStatus } from './db/migrations.ts';

export type { FailureClass, RunStatus };

export const ASSISTANT_IDS = ['copilot', 'cursor', 'claude_code', 'codex'] as const;
export type AssistantId = (typeof ASSISTANT_IDS)[number];

export const CAPABILITY_STATUSES = [
  'supported',
  'requires_authentication',
  'requires_manual_execution',
  'not_configured',
  'unsupported',
] as const;
export type CapabilityStatus = (typeof CAPABILITY_STATUSES)[number];

/** Failure-mode taxonomy from the research synopsis; labels are applied by researchers. */
export const FAILURE_MODES = [
  'misunderstood_requirements',
  'repository_context_error',
  'incomplete_implementation',
  'dependency_issue',
  'repeated_failed_attempts',
  'regression_introduced',
  'security_weakness',
  'scope_violation',
  'other',
] as const;
export type FailureMode = (typeof FAILURE_MODES)[number];

export interface TaskRecord {
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
  prompt: string;
  metadata: Record<string, unknown>;
  syncedAt: string;
}

export interface AssistantRecord {
  id: AssistantId;
  name: string;
  vendor: string;
  interface: string;
  capabilityStatus: CapabilityStatus;
  capabilityDetail: string | null;
  detectedVersion: string | null;
  operatorReportedVersion: string | null;
  operatorReportedModel: string | null;
  checkedAt: string | null;
}

export interface ExperimentRecord {
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
  config: Record<string, unknown>;
  createdBy: string;
  machineId: string;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface PlannedAttempt {
  id: string;
  experimentId: string;
  taskId: string;
  taskHash: string;
  promptHash: string;
  assistantId: AssistantId;
  attemptNumber: number;
  sequence: number;
  timeLimitSeconds: number;
}

export interface RunRecord {
  id: string;
  plannedAttemptId: string;
  experimentId: string;
  taskId: string;
  assistantId: AssistantId;
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
  assistantVersionSource: 'detected' | 'operator' | 'unknown';
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
  failureClass: FailureClass | null;
  errorMessage: string | null;
  failureModes: string[];
  invalidationReason: string | null;
  success: boolean | null;
  outcome: string | null;
  latestEvaluationId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface EvaluationRecord {
  id: string;
  runId: string;
  status: 'queued' | 'running' | 'completed' | 'error';
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
  artifactDir: string | null;
  toolVersions: Record<string, unknown>;
  queuedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface EventRecord {
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
