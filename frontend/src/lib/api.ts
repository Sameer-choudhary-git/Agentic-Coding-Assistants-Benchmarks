import type {
  Assistant,
  EventItem,
  EvidenceRegistry,
  GoldenOverview,
  Experiment,
  PlannedAttempt,
  Progress,
  Run,
  RunDetail,
  Summary,
  Task,
} from './types.ts';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
  }
}

const BASE = '/api/v1';

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + url, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'network', 'Cannot reach the backend. Start it with "npm run dev" and reload this page.');
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = data?.error ?? {};
    const details = Array.isArray(err.details)
      ? err.details
          .map((d: { path?: string[]; message?: string }) =>
            d.path?.length ? `${d.path.join('.')}: ${d.message}` : (d.message ?? String(d)),
          )
          .join('; ')
      : err.details && typeof err.details === 'object'
        ? JSON.stringify(err.details)
        : '';
    throw new ApiError(res.status, err.code ?? 'error', `${err.message ?? res.statusText}${details ? ` (${details})` : ''}`, err.details);
  }
  return data as T;
}

export interface ExperimentInput {
  name: string;
  description?: string;
  taskIds: string[];
  assistantIds: string[];
  attempts: number;
  executionMode: 'human' | 'automated';
  evalMode?: 'docker' | 'local';
  timeLimitOverrideMinutes: number | null;
  randomizeOrder: boolean;
  seed?: number;
  allowUnvalidatedTasks?: boolean;
}

export interface ExperimentPreview {
  plannedAttempts: number;
  tasks: number;
  assistants: number;
  attempts: number;
  formula: string;
  unvalidatedTasks: string[];
  unknownTasks: string[];
  evalMode: 'docker' | 'local';
  benchmark?: string | null;
  warnings: string[];
}

/** Build a query string from the defined values only. */
export function query(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => Boolean(e[1])));
  const str = q.toString();
  return str ? `?${str}` : '';
}

export const api = {
  health: () =>
    request<{
      status: string;
      version: string;
      tasks: number;
      evalMode: string;
      automationEnabled: boolean;
      operator: string;
      machineId: string;
      workspaceRoot: string;
    }>('GET', '/health'),
  evaluatorHealth: (mode?: string) => request<Record<string, any>>('GET', `/health/evaluator${mode ? `?mode=${mode}` : ''}`),
  tasks: () => request<{ tasks: Task[] }>('GET', '/tasks'),
  task: (id: string) => request<{ task: Task; versions: Record<string, string>[] }>('GET', `/tasks/${encodeURIComponent(id)}`),
  starterFile: (id: string, path: string) =>
    request<{ path: string; content: string }>('GET', `/tasks/${encodeURIComponent(id)}/starter?path=${encodeURIComponent(path)}`),
  syncTasks: () => request<{ count: number }>('POST', '/tasks/sync'),
  assistants: () => request<{ assistants: Assistant[] }>('GET', '/assistants'),
  evidence: () => request<EvidenceRegistry>('GET', '/evidence'),
  golden: () => request<GoldenOverview>('GET', '/golden'),
  detectAssistants: () => request<{ assistants: Assistant[] }>('POST', '/assistants/detect'),
  updateAssistant: (id: string, version: string | null, model: string | null) =>
    request<{ assistant: Assistant }>('PATCH', `/assistants/${id}`, { version, model }),
  experiments: () => request<{ experiments: Experiment[] }>('GET', '/experiments'),
  experiment: (id: string) =>
    request<{ experiment: Experiment; progress: Progress; plannedAttempts: PlannedAttempt[]; runs: Run[] }>('GET', `/experiments/${id}`),
  previewExperiment: (input: ExperimentInput) => request<ExperimentPreview>('POST', '/experiments/preview', input),
  createExperiment: (input: ExperimentInput) => request<{ experiment: Experiment; plannedAttempts: number }>('POST', '/experiments', input),
  startExperiment: (id: string) => request<{ experiment: Experiment }>('POST', `/experiments/${id}/start`),
  setExperimentStatus: (id: string, status: 'completed' | 'archived') =>
    request<{ experiment: Experiment }>('POST', `/experiments/${id}/status`, { status }),
  runs: (q: Record<string, string | undefined> = {}) => {
    const params = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
    return request<{ runs: Run[] }>('GET', `/runs${params.size ? `?${params}` : ''}`);
  },
  run: (id: string) => request<RunDetail>('GET', `/runs/${id}`),
  prepare: (id: string) => request<{ run: Run }>('POST', `/runs/${id}/prepare`),
  start: (id: string, body: { assistantVersion?: string; model?: string }) => request<{ run: Run }>('POST', `/runs/${id}/start`, body),
  log: (id: string, type: 'iteration' | 'intervention' | 'note', note: string) =>
    request<{ run: Run }>('POST', `/runs/${id}/log`, { type, note }),
  stop: (id: string) => request<{ run: Run }>('POST', `/runs/${id}/stop`),
  submit: (id: string, body: Record<string, unknown>) => request<{ run: Run }>('POST', `/runs/${id}/submit`, body),
  evaluate: (id: string) => request<{ evaluationId: string; run: Run }>('POST', `/runs/${id}/evaluate`),
  automate: (id: string) => request<{ run: Run }>('POST', `/runs/${id}/automate`),
  retry: (id: string) => request<{ run: Run }>('POST', `/runs/${id}/retry`),
  fail: (id: string, failureClass: string, message: string) => request<{ run: Run }>('POST', `/runs/${id}/fail`, { failureClass, message }),
  invalidate: (id: string, reason: string) => request<{ run: Run }>('POST', `/runs/${id}/invalidate`, { reason }),
  label: (id: string, body: { failureModes?: string[]; notes?: string }) => request<{ run: Run }>('PATCH', `/runs/${id}/labels`, body),
  summary: (experimentId?: string, benchmark?: string) => request<Summary>('GET', `/results/summary${query({ experimentId, benchmark })}`),
  records: (experimentId?: string, benchmark?: string) =>
    request<{ records: Record<string, any>[] }>('GET', `/results/records${query({ experimentId, benchmark })}`),
  exportAll: (experimentId?: string) =>
    request<{ directory: string; files: { name: string; sha256: string; bytes: number }[] }>('POST', '/results/export-all', {
      experimentId,
    }),
  importBundle: (bundle: unknown) =>
    request<{
      inserted: Record<string, number>;
      skippedIdentical: Record<string, number>;
      conflicts: { table: string; id: string; reason: string }[];
      warnings: string[];
    }>('POST', '/results/import', bundle),
  events: (limit = 15) => request<{ events: EventItem[] }>('GET', `/events?limit=${limit}`),
};

export const exportUrl = (format: string, experimentId?: string) =>
  `${BASE}/results/export?format=${format}${experimentId ? `&experimentId=${experimentId}` : ''}`;
export const artifactUrl = (runId: string, artifactId: string) => `${BASE}/runs/${runId}/artifacts/${artifactId}`;
export const goldenFigureUrl = (name: string) => `${BASE}/golden/figures/${encodeURIComponent(name)}`;
export const evidenceExportUrl = (format: 'csv' | 'latex' | 'json') => `${BASE}/evidence/export?format=${format}`;
