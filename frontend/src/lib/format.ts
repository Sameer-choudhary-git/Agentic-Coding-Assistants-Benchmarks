import type { RunStatus } from './types.ts';

export const ASSISTANTS: { id: string; name: string; short: string; color: string }[] = [
  { id: 'copilot', name: 'GitHub Copilot', short: 'Copilot', color: 'var(--color-copilot)' },
  { id: 'cursor', name: 'Cursor', short: 'Cursor', color: 'var(--color-cursor)' },
  { id: 'claude_code', name: 'Claude Code', short: 'Claude', color: 'var(--color-claude)' },
  { id: 'codex', name: 'OpenAI Codex', short: 'Codex', color: 'var(--color-codex)' },
];

export const assistantName = (id: string) => ASSISTANTS.find((a) => a.id === id)?.name ?? id;
export const assistantColor = (id: string) => ASSISTANTS.find((a) => a.id === id)?.color ?? 'var(--color-ink-faint)';

export const CATEGORIES: { id: string; label: string }[] = [
  { id: 'bug_fixing', label: 'Bug fixing' },
  { id: 'feature_implementation', label: 'Feature implementation' },
  { id: 'security_remediation', label: 'Security remediation' },
  { id: 'refactoring', label: 'Refactoring' },
  { id: 'test_writing', label: 'Test writing' },
  { id: 'repository_reasoning', label: 'Repository reasoning' },
];
/** Categories of the golden benchmark: the golden dataset's domains, named like the custom suite where one matches. */
export const GOLDEN_CATEGORIES = [
  { id: 'bug_fixing', label: 'Bug fixing' },
  { id: 'feature_implementation', label: 'Feature implementation' },
  { id: 'performance', label: 'Performance' },
  { id: 'refactoring', label: 'Refactoring' },
  { id: 'security_remediation', label: 'Security remediation' },
  { id: 'frontend_visual', label: 'Frontend / visual' },
];
export const categoriesFor = (benchmark: string | null | undefined) =>
  benchmark === 'golden' ? GOLDEN_CATEGORIES : CATEGORIES;
export const categoryLabel = (id: string) =>
  id === 'swebench_verified'
    ? 'SWE-bench Verified'
    : (CATEGORIES.find((c) => c.id === id)?.label ?? GOLDEN_CATEGORIES.find((c) => c.id === id)?.label ?? id);

/** The benchmarks the platform runs: the 18-task custom suite, the SWE-bench Verified pilot and the golden set. */
export const BENCHMARKS: { id: string; label: string; blurb: string }[] = [
  { id: 'custom', label: 'Custom suite', blurb: '18 synthetic Python tasks in six categories, scored by hidden tests' },
  { id: 'swebench_verified', label: 'SWE-bench Verified', blurb: 'Real GitHub issues, scored by the official SWE-bench harness' },
  {
    id: 'golden',
    label: 'Golden',
    blurb:
      'Golden-dataset tasks in six domains (SWE-bench Verified, Multilingual, Multimodal and Pro), scored by hidden tests in Docker. Use the balanced core for a domain-balanced study',
  },
];
/** Benchmarks whose tasks are real repositories scored by the SWE-bench harness. */
export const isHarnessBenchmark = (id: string | null | undefined) => id === 'swebench_verified' || id === 'golden';
/** Golden tasks in the seeded, domain-balanced core subset. */
export const isGoldenCore = (t: { metadata: { swebench?: { golden?: { core?: boolean } | null } | null } }) =>
  Boolean(t.metadata.swebench?.golden?.core);
export const benchmarkLabel = (id: string | null | undefined) => BENCHMARKS.find((b) => b.id === id)?.label ?? 'All benchmarks';
export const taskBenchmark = (t: { kind: string; metadata: { benchmark?: string } }) =>
  t.metadata.benchmark ?? (t.kind === 'swebench' ? 'swebench_verified' : 'custom');
export const isSwebench = (t: { kind: string } | null | undefined) => t?.kind === 'swebench';

export const STATUS_LABEL: Record<RunStatus, string> = {
  planned: 'Planned',
  ready: 'Ready',
  running: 'Running',
  awaiting_human: 'Awaiting human action',
  submitted: 'Submitted',
  evaluating: 'Evaluating',
  completed: 'Completed',
  failed: 'Failed',
  invalidated: 'Invalidated',
};

export const FAILURE_CLASS_LABEL: Record<string, string> = {
  task_failure: 'Task failure',
  timeout: 'Time limit exceeded',
  evaluator_error: 'Evaluator failure',
  adapter_error: 'Adapter failure',
  environment_error: 'Environment failure',
  operator_abort: 'Aborted by operator',
  invalid: 'Invalid experiment',
};

export const FAILURE_MODES: { id: string; label: string }[] = [
  { id: 'misunderstood_requirements', label: 'Misunderstood requirements' },
  { id: 'repository_context_error', label: 'Repository context error' },
  { id: 'incomplete_implementation', label: 'Incomplete implementation' },
  { id: 'dependency_issue', label: 'Dependency issue' },
  { id: 'repeated_failed_attempts', label: 'Repeated failed attempts' },
  { id: 'regression_introduced', label: 'Regression introduced' },
  { id: 'security_weakness', label: 'Security weakness' },
  { id: 'scope_violation', label: 'Changed files outside scope' },
  { id: 'other', label: 'Other' },
];

export const CAPABILITY_LABEL: Record<string, string> = {
  supported: 'Supported',
  requires_authentication: 'Requires authentication',
  requires_manual_execution: 'Requires manual execution',
  not_configured: 'Not configured',
  unsupported: 'Unsupported',
};

export function pct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return Number.isInteger(value) ? String(value) : value.toFixed(digits);
}

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rest = s % 60;
  if (m >= 60) return `${Math.floor(m / 60)} h ${m % 60} min`;
  return m ? `${m} min ${rest.toString().padStart(2, '0')} s` : `${rest} s`;
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function shortHash(hash: string | null | undefined, n = 10): string {
  return hash ? hash.slice(0, n) : '—';
}

export function shortId(id: string): string {
  return id.replace(/-/g, '').slice(0, 8);
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** Same formula as the backend preview: tasks × assistants × attempts. */
export function plannedAttemptCount(tasks: number, assistants: number, attempts: number): number {
  return Math.max(0, tasks) * Math.max(0, assistants) * Math.max(0, attempts);
}

/** Order categories as in the research design rather than alphabetically. */
export function byCategoryOrder<T extends { category: string }>(rows: T[]): T[] {
  const index = (id: string) => {
    const i = CATEGORIES.findIndex((c) => c.id === id);
    return i === -1 ? 99 : i;
  };
  return [...rows].sort((a, b) => index(a.category) - index(b.category));
}

/** Axis label for a duration in seconds: seconds below two minutes, minutes above. */
export function axisDuration(seconds: number, domainMax: number): string {
  return domainMax < 120 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min`;
}
