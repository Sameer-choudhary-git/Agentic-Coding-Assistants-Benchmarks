import { ASSISTANTS, assistantName, categoryLabel, STATUS_LABEL } from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { PlannedAttempt, Run } from '../lib/types.ts';
import { cx } from './ui.tsx';

export type CellState = 'not_started' | 'pending' | 'in_progress' | 'passed' | 'not_passed' | 'failed' | 'invalidated';

export function cellState(run: Run | undefined): CellState {
  if (!run || run.status === 'planned' || run.status === 'ready') return run ? 'pending' : 'not_started';
  if (run.status === 'completed') return run.success ? 'passed' : 'not_passed';
  if (run.status === 'failed') return 'failed';
  if (run.status === 'invalidated') return 'invalidated';
  return 'in_progress';
}

const CELL: Record<CellState, { cls: string; label: string }> = {
  not_started: { cls: 'bg-panel border-rule', label: 'Not started' },
  pending: { cls: 'bg-panel border-rule-strong', label: 'Planned or workspace ready' },
  in_progress: { cls: 'bg-pending-tint border-pending', label: 'In progress (running, awaiting action, submitted or evaluating)' },
  passed: { cls: 'bg-pass border-pass', label: 'Evaluated: passed' },
  not_passed: { cls: 'bg-fail border-fail', label: 'Evaluated: did not pass' },
  failed: {
    cls: 'bg-panel border-fail [background-image:repeating-linear-gradient(45deg,var(--color-fail-tint)_0_3px,transparent_3px_6px)]',
    label: 'Operational failure (excluded from success rate)',
  },
  invalidated: { cls: 'bg-void-tint border-void', label: 'Invalidated' },
};

/**
 * The experiment matrix: one row per task, one column group per assistant, one cell per attempt.
 * Cells show the state of the *effective* (latest) run of each planned attempt.
 */
export function ExperimentMatrix({ planned, runs, compact = false }: { planned: PlannedAttempt[]; runs: Run[]; compact?: boolean }) {
  const latest = new Map<string, Run>();
  for (const r of runs) {
    const cur = latest.get(r.plannedAttemptId);
    if (!cur || r.runNumber > cur.runNumber) latest.set(r.plannedAttemptId, r);
  }
  const tasks = [...new Set(planned.map((p) => p.taskId))].sort();
  const assistants = ASSISTANTS.filter((a) => planned.some((p) => p.assistantId === a.id));
  const attempts = Math.max(1, ...planned.map((p) => p.attemptNumber));
  const lookup = new Map(planned.map((p) => [`${p.taskId}|${p.assistantId}|${p.attemptNumber}`, p]));
  const size = compact ? 'size-3.5' : 'size-5';
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0 text-xs" aria-label="Experiment matrix">
          <thead>
            <tr>
              <th className="pr-3 text-left font-medium text-ink-soft">Task</th>
              {assistants.map((a) => (
                <th key={a.id} colSpan={attempts} className="px-2 pb-1 text-left font-medium" style={{ color: a.color }}>
                  {compact ? a.short : a.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tasks.map((taskId) => (
              <tr key={taskId}>
                <th scope="row" className="whitespace-nowrap pr-3 text-left font-mono font-normal text-ink-soft">
                  {taskId}
                </th>
                {assistants.map((a) =>
                  Array.from({ length: attempts }, (_, i) => {
                    const p = lookup.get(`${taskId}|${a.id}|${i + 1}`);
                    const run = p ? latest.get(p.id) : undefined;
                    const state = cellState(run);
                    const title = `${taskId}, ${assistantName(a.id)}, attempt ${i + 1}: ${run ? STATUS_LABEL[run.status] : 'not started'}${run && run.runNumber > 1 ? ` (retry ${run.runNumber - 1})` : ''}`;
                    const cell = <span className={cx('block rounded-[2px] border', size, CELL[state].cls)} />;
                    return (
                      <td key={`${a.id}-${i}`} className={cx('py-0.5', i === 0 ? 'pl-2' : 'pl-0.5')} title={title}>
                        {run ? (
                          <Link to={`/runs/${run.id}`} title={title} className="block">
                            {cell}
                            <span className="sr-only">{title}</span>
                          </Link>
                        ) : p ? (
                          cell
                        ) : null}
                      </td>
                    );
                  }),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft" aria-label="Matrix legend">
        {(Object.keys(CELL) as CellState[]).map((k) => (
          <li key={k} className="flex items-center gap-1.5">
            <span className={cx('inline-block size-3 rounded-[2px] border', CELL[k].cls)} />
            {CELL[k].label}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function categoryOf(taskId: string): string {
  const prefix = taskId.split('-')[0];
  const map: Record<string, string> = {
    BF: 'bug_fixing',
    FI: 'feature_implementation',
    SR: 'security_remediation',
    RF: 'refactoring',
    TW: 'test_writing',
    RR: 'repository_reasoning',
  };
  if (taskId.includes('__')) return categoryLabel('swebench_verified');
  return categoryLabel(map[prefix] ?? prefix);
}
