import { useEffect, useMemo, useState } from 'react';
import { ExperimentMatrix } from '../components/Matrix.tsx';
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorBox,
  Field,
  Info,
  inputClass,
  Loading,
  Notice,
  PageHeader,
  Section,
  StatusBadge,
  Table,
} from '../components/ui.tsx';
import { api, type ExperimentInput, type ExperimentPreview } from '../lib/api.ts';
import { BenchmarkSwitch } from '../components/BenchmarkSwitch.tsx';
import {
  ASSISTANTS,
  assistantName,
  BENCHMARKS,
  categoriesFor,
  dateTime,
  FAILURE_CLASS_LABEL,
  isHarnessBenchmark,
  plannedAttemptCount,
  STATUS_LABEL,
  taskBenchmark,
} from '../lib/format.ts';
import { Link, useRouter } from '../lib/router.tsx';
import type { Experiment, Run, RunStatus, Task } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

const EXP_STATUS: Record<Experiment['status'], string> = {
  planned: 'Planned',
  active: 'Active',
  completed: 'Completed',
  archived: 'Archived',
};

export function Experiments() {
  const state = useAsync(() => api.experiments(), [], 10_000);
  return (
    <>
      <PageHeader
        title="Experiments"
        actions={
          <Link
            to="/experiments/new"
            className="rounded border border-action bg-action px-3 py-1.5 text-sm font-medium text-white hover:bg-action-strong"
          >
            New experiment
          </Link>
        }
      >
        An experiment fixes the task versions, assistants, attempts per pair, time limits and evaluation mode. Its configuration is recorded
        when it is created and cannot change afterwards.
      </PageHeader>
      {state.error ? <ErrorBox error={state.error} onRetry={state.reload} /> : null}
      {!state.data ? (
        <Loading label="Loading experiments" />
      ) : state.data.experiments.length === 0 ? (
        <EmptyState title="No experiments yet">
          Create one to generate the planned attempt matrix. Custom suite: 18 tasks × 4 assistants × 2 attempts = 144 attempts. SWE-bench
          Verified pilot: 12 tasks × 4 assistants × 1 attempt = 48 attempts. Golden set: up to 67 tasks × 4 assistants × 1 attempt.
          Each experiment uses one benchmark.
        </EmptyState>
      ) : (
        <Table caption="Experiments">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th className="text-right">Planned</th>
              <th className="text-right">Completed</th>
              <th>Mode</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {state.data.experiments.map((e) => (
              <tr key={e.id} className="hover:bg-paper">
                <td>
                  <Link to={`/experiments/${e.id}`} className="font-medium text-action hover:underline">
                    {e.name}
                  </Link>
                </td>
                <td>{EXP_STATUS[e.status]}</td>
                <td className="text-right">{e.progress?.planned}</td>
                <td className="text-right">{e.progress?.completed}</td>
                <td className="text-xs">
                  {e.executionMode === 'human' ? 'Human-operated' : 'Automated'}, {e.evalMode} evaluation
                </td>
                <td className="text-xs">
                  {dateTime(e.createdAt)} by {e.createdBy}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </>
  );
}

export function NewExperiment() {
  const { navigate } = useRouter();
  const tasks = useAsync(() => api.tasks(), []);
  const health = useAsync(() => api.health(), []);
  const [benchmark, setBenchmark] = useState('custom');
  const [name, setName] = useState('Full study');
  const [description, setDescription] = useState('');
  const [taskIds, setTaskIds] = useState<string[] | null>(null);
  const [assistantIds, setAssistantIds] = useState<string[]>(ASSISTANTS.map((a) => a.id));
  const [attempts, setAttempts] = useState(2);
  const [executionMode, setExecutionMode] = useState<'human' | 'automated'>('human');
  const [evalMode, setEvalMode] = useState<'docker' | 'local' | ''>('');
  const [override, setOverride] = useState('');
  const [randomize, setRandomize] = useState(true);
  const [seed, setSeed] = useState('');
  const [allowUnvalidated, setAllowUnvalidated] = useState(false);
  const [preview, setPreview] = useState<ExperimentPreview>();
  const [error, setError] = useState<string>();
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (tasks.data && taskIds === null) setTaskIds(tasks.data.tasks.filter((t) => taskBenchmark(t) === 'custom').map((t) => t.id));
  }, [tasks.data, taskIds]);

  const input: ExperimentInput = useMemo(
    () => ({
      name,
      description,
      taskIds: taskIds ?? [],
      assistantIds,
      attempts,
      executionMode,
      evalMode: evalMode || undefined,
      timeLimitOverrideMinutes: override ? Number(override) : null,
      randomizeOrder: randomize,
      seed: seed ? Number(seed) : undefined,
      allowUnvalidatedTasks: allowUnvalidated,
    }),
    [name, description, taskIds, assistantIds, attempts, executionMode, evalMode, override, randomize, seed, allowUnvalidated],
  );

  const localCount = plannedAttemptCount(input.taskIds.length, assistantIds.length, attempts);
  const problems: string[] = [];
  if (name.trim().length < 3) problems.push('Name must have at least 3 characters.');
  if (!input.taskIds.length) problems.push('Select at least one task.');
  if (!assistantIds.length) problems.push('Select at least one assistant.');
  if (attempts < 1 || attempts > 10) problems.push('Attempts must be between 1 and 10.');
  if (override && (Number(override) < 1 || Number(override) > 240)) problems.push('Time limit override must be 1–240 minutes.');

  useEffect(() => {
    if (problems.length) return;
    const t = setTimeout(() => {
      api
        .previewExperiment(input)
        .then(setPreview)
        .catch((e) => setError((e as Error).message));
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input]);

  if (tasks.error) return <ErrorBox error={tasks.error} onRetry={tasks.reload} />;
  if (!tasks.data || taskIds === null) return <Loading label="Loading tasks" />;
  const all = tasks.data.tasks.filter((t) => taskBenchmark(t) === benchmark);
  const counts = Object.fromEntries(BENCHMARKS.map((b) => [b.id, tasks.data!.tasks.filter((t) => taskBenchmark(t) === b.id).length]));
  const chooseBenchmark = (b: string) => {
    setBenchmark(b);
    setTaskIds(tasks.data!.tasks.filter((t) => taskBenchmark(t) === b).map((t) => t.id));
    setAttempts(isHarnessBenchmark(b) ? 1 : 2);
    setName(b === 'swebench_verified' ? 'SWE-bench Verified pilot' : b === 'golden_verified' ? 'Golden set study' : 'Full study');
  };
  const groups =
    benchmark === 'swebench_verified'
      ? ['easy', 'medium', 'hard'].map((d) => ({
          id: d,
          label: `${d[0].toUpperCase()}${d.slice(1)} (leaderboard tertile)`,
          match: (t: Task) => t.difficulty === d,
        }))
      : categoriesFor(benchmark).map((c) => ({ id: c.id, label: c.label, match: (t: Task) => t.category === c.id }));
  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  return (
    <>
      <PageHeader title="New experiment" crumbs={[{ label: 'Experiments', to: '/experiments' }, { label: 'New' }]}>
        Choose tasks, assistants and attempts. The planned attempt count updates as you change the selection.
      </PageHeader>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <form
          className="space-y-6"
          onSubmit={(e) => {
            e.preventDefault();
            if (!problems.length) setConfirm(true);
          }}
        >
          <div>
            <p className="mb-2 text-sm font-medium">Benchmark</p>
            <BenchmarkSwitch value={benchmark} onChange={chooseBenchmark} counts={counts} />
            <p className="mt-1.5 text-xs text-ink-faint">
              {BENCHMARKS.find((b) => b.id === benchmark)?.blurb}. An experiment uses one benchmark.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" error={name.trim().length < 3 ? 'At least 3 characters' : undefined}>
              <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Description" hint="Optional: purpose, protocol version, operator plan">
              <input className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          </div>

          <fieldset>
            <legend className="mb-2 flex w-full items-baseline justify-between text-sm font-medium">
              <span>
                Tasks ({input.taskIds.length} of {all.length})
              </span>
              <span className="flex gap-2">
                <button type="button" className="text-action hover:underline" onClick={() => setTaskIds(all.map((t) => t.id))}>
                  Select all
                </button>
                <button type="button" className="text-action hover:underline" onClick={() => setTaskIds([])}>
                  Clear
                </button>
              </span>
            </legend>
            <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {groups.map((c) => (
                <div key={c.id}>
                  <p className="mb-1 text-sm text-ink-soft">{c.label}</p>
                  {all.filter(c.match).map((t) => (
                    <label key={t.id} className="flex items-start gap-2 py-0.5 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={input.taskIds.includes(t.id)}
                        onChange={() => setTaskIds(toggle(input.taskIds, t.id))}
                      />
                      <span>
                        <span className="font-mono text-xs">{t.id}</span> {t.title}
                        {t.validationStatus !== 'validated' ? (
                          <span className="ml-1 text-xs text-fail">({t.validationStatus.replace(/_/g, ' ')})</span>
                        ) : null}
                      </span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-2 text-sm font-medium">Assistants ({assistantIds.length})</legend>
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              {ASSISTANTS.map((a) => (
                <label key={a.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={assistantIds.includes(a.id)}
                    onChange={() => setAssistantIds(toggle(assistantIds, a.id))}
                  />
                  <span className="inline-block size-2.5 rounded-full" style={{ background: a.color }} />
                  {a.name}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Attempts per task and assistant">
              <input
                type="number"
                min={1}
                max={10}
                className={inputClass}
                value={attempts}
                onChange={(e) => setAttempts(Number(e.target.value))}
              />
            </Field>
            <Field label="Execution mode" hint="Human-operated works for every assistant">
              <select
                className={inputClass}
                value={executionMode}
                onChange={(e) => setExecutionMode(e.target.value as 'human' | 'automated')}
              >
                <option value="human">Human-operated</option>
                <option value="automated">Automated where supported</option>
              </select>
            </Field>
            <Field label="Evaluation mode" hint={`Default from server: ${health.data?.evalMode ?? '…'}`}>
              <select className={inputClass} value={evalMode} onChange={(e) => setEvalMode(e.target.value as 'docker' | 'local' | '')}>
                <option value="">Server default</option>
                <option value="docker">Docker sandbox</option>
                <option value="local">Local subprocess (no isolation)</option>
              </select>
            </Field>
            <Field label="Time limit override (minutes)" hint="Empty: each task's own limit">
              <input
                type="number"
                min={1}
                max={240}
                className={inputClass}
                value={override}
                onChange={(e) => setOverride(e.target.value)}
              />
            </Field>
            <Field label="Run order seed" hint="Empty: random seed, recorded for reproducibility">
              <input type="number" min={0} className={inputClass} value={seed} onChange={(e) => setSeed(e.target.value)} />
            </Field>
            <div className="space-y-2 pt-6 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={randomize} onChange={(e) => setRandomize(e.target.checked)} />
                Randomise run order
                <Info>
                  Interleaving tasks and assistants reduces order effects such as operator fatigue or learning. The seed makes the order
                  reproducible.
                </Info>
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={allowUnvalidated} onChange={(e) => setAllowUnvalidated(e.target.checked)} />
                Allow unvalidated tasks (exploratory only)
              </label>
            </div>
          </div>
          {problems.length ? (
            <ul className="list-disc pl-5 text-sm text-fail">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : null}
          <Button type="submit" variant="primary" disabled={problems.length > 0}>
            Review and create
          </Button>
        </form>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <div className="rounded border border-rule bg-panel p-5">
            <p className="text-sm text-ink-soft">Planned attempts</p>
            <p className="tabular text-5xl font-semibold leading-none tracking-tight">
              {preview && !problems.length ? preview.plannedAttempts : localCount}
            </p>
            <p className="mt-2 text-sm text-ink-soft">
              {input.taskIds.length} tasks × {assistantIds.length} assistants × {attempts} attempts
            </p>
            <p className="mt-3 text-xs text-ink-faint">Planned attempts are not results. Nothing is measured until a run is evaluated.</p>
            {preview?.unvalidatedTasks.length ? (
              <p className="mt-3 text-sm text-fail">Not validated: {preview.unvalidatedTasks.join(', ')}</p>
            ) : null}
            {preview?.warnings.map((w) => (
              <p key={w} className="mt-3 text-sm text-pending">
                {w}
              </p>
            ))}
            {error ? <p className="mt-3 text-sm text-fail">{error}</p> : null}
          </div>
        </aside>
      </div>
      <ConfirmDialog
        open={confirm}
        title="Create this experiment?"
        confirmLabel="Create experiment"
        body={
          <>
            This records {preview?.plannedAttempts ?? localCount} planned attempts with the current task versions and prompt hashes. The
            configuration cannot be edited afterwards.
          </>
        }
        onClose={() => setConfirm(false)}
        onConfirm={async () => {
          const created = await api.createExperiment(input);
          navigate(`/experiments/${created.experiment.id}`);
        }}
      />
    </>
  );
}

const STATUS_FILTERS: (RunStatus | '')[] = [
  '',
  'planned',
  'ready',
  'running',
  'awaiting_human',
  'submitted',
  'evaluating',
  'completed',
  'failed',
  'invalidated',
];

export function RunTable({ runs, showExperiment = false }: { runs: Run[]; showExperiment?: boolean }) {
  if (!runs.length) return <EmptyState title="No runs match">Change the filters or start the experiment to create runs.</EmptyState>;
  return (
    <Table caption="Runs">
      <thead>
        <tr>
          <th>Run</th>
          <th>Task</th>
          <th>Assistant</th>
          <th className="text-right">Attempt</th>
          <th>Status</th>
          <th>Outcome</th>
          <th>Updated</th>
          {showExperiment ? <th>Experiment</th> : null}
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id} className="hover:bg-paper">
            <td className="font-mono text-xs">
              <Link to={`/runs/${r.id}`} className="text-action hover:underline">
                {r.id.slice(0, 8)}
              </Link>
              {r.runNumber > 1 ? <span className="ml-1 text-ink-faint">retry {r.runNumber - 1}</span> : null}
            </td>
            <td className="font-mono text-xs">{r.taskId}</td>
            <td>{assistantName(r.assistantId)}</td>
            <td className="tabular text-right">{r.attemptNumber}</td>
            <td>
              <StatusBadge status={r.status} />
            </td>
            <td className="text-xs">
              {r.status === 'completed' ? (
                r.success ? (
                  <span className="font-medium text-pass">Passed</span>
                ) : (
                  <span className="text-fail">{FAILURE_CLASS_LABEL[r.failureClass ?? ''] ?? 'Did not pass'}</span>
                )
              ) : r.failureClass ? (
                <span className="text-fail">{FAILURE_CLASS_LABEL[r.failureClass]}</span>
              ) : (
                <span className="text-ink-faint">—</span>
              )}
              {r.errorMessage && r.status === 'failed' ? (
                <div className="max-w-xs truncate text-ink-faint" title={r.errorMessage}>
                  {r.errorMessage}
                </div>
              ) : null}
            </td>
            <td className="whitespace-nowrap text-xs">{dateTime(r.updatedAt)}</td>
            {showExperiment ? (
              <td className="font-mono text-xs">
                <Link to={`/experiments/${r.experimentId}`} className="text-action hover:underline">
                  {r.experimentId.slice(0, 8)}
                </Link>
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function ExperimentDetail({ id }: { id: string }) {
  const state = useAsync(() => api.experiment(id), [id], 5_000);
  const [status, setStatus] = useState<RunStatus | ''>('');
  const [assistant, setAssistant] = useState('');
  const [confirm, setConfirm] = useState<'start' | 'complete' | null>(null);
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Loading experiment" />;
  const { experiment: e, progress, plannedAttempts, runs } = state.data;
  const filtered = runs.filter((r) => (!status || r.status === status) && (!assistant || r.assistantId === assistant));
  const nextRun = runs.find((r) => r.status === 'planned' || r.status === 'ready');
  return (
    <>
      <PageHeader
        title={e.name}
        crumbs={[{ label: 'Experiments', to: '/experiments' }, { label: e.name }]}
        actions={
          <>
            {e.status === 'planned' ? (
              <Button variant="primary" onClick={() => setConfirm('start')}>
                Start experiment
              </Button>
            ) : null}
            {e.status === 'active' && nextRun ? (
              <Link
                to={`/runs/${nextRun.id}`}
                className="rounded border border-action bg-action px-3 py-1.5 text-sm font-medium text-white hover:bg-action-strong"
              >
                Open next run in order
              </Link>
            ) : null}
            {e.status === 'active' ? <Button onClick={() => setConfirm('complete')}>Mark completed</Button> : null}
          </>
        }
      >
        {e.description || 'No description.'} {e.executionMode === 'human' ? 'Human-operated' : 'Automated where supported'}, {e.evalMode}{' '}
        evaluation, {e.randomizeOrder ? `randomised order (seed ${e.seed})` : 'fixed order'}.
      </PageHeader>
      {e.evalMode === 'local' ? (
        <div className="mb-6">
          <Notice tone="warn">
            This experiment uses local evaluation: submitted code runs on this machine without sandboxing. Prefer Docker for official runs.
          </Notice>
        </div>
      ) : null}
      <Section title="Progress" aside={`${progress.totalRuns} run records, ${progress.retries} retries`}>
        <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
          <div>
            <dt className="text-ink-soft">Planned attempts</dt>
            <dd className="tabular text-xl font-semibold">{progress.planned}</dd>
          </div>
          {(Object.keys(STATUS_LABEL) as RunStatus[]).map((s) => (
            <div key={s}>
              <dt className="text-ink-soft">{STATUS_LABEL[s]}</dt>
              <dd className="tabular text-xl font-semibold">{progress.byStatus[s] ?? 0}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-void-tint" aria-hidden>
          <div className="h-full bg-pass" style={{ width: `${progress.planned ? (100 * progress.completed) / progress.planned : 0}%` }} />
        </div>
      </Section>
      <Section title="Experiment matrix" aside="Each cell is the latest run of one planned attempt">
        <ExperimentMatrix planned={plannedAttempts} runs={runs} />
      </Section>
      <Section title="Runs">
        <div className="mb-3 flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="mr-2 text-ink-soft">Status</span>
            <select className={`${inputClass} w-auto`} value={status} onChange={(ev) => setStatus(ev.target.value as RunStatus | '')}>
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {s ? STATUS_LABEL[s] : 'All'}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mr-2 text-ink-soft">Assistant</span>
            <select className={`${inputClass} w-auto`} value={assistant} onChange={(ev) => setAssistant(ev.target.value)}>
              <option value="">All</option>
              {ASSISTANTS.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {e.status === 'planned' ? (
          <EmptyState title="The experiment has not started">Start it to create one run per planned attempt.</EmptyState>
        ) : (
          <RunTable runs={filtered} />
        )}
      </Section>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm === 'start' ? 'Start this experiment?' : 'Mark this experiment as completed?'}
        confirmLabel={confirm === 'start' ? 'Start experiment' : 'Mark completed'}
        body={
          confirm === 'start'
            ? `Creates ${progress.planned} runs in the Planned state. Workspaces are created one run at a time when you prepare them.`
            : 'Runs can no longer be prepared, started or retried. Results stay available.'
        }
        onClose={() => setConfirm(null)}
        onConfirm={async () => {
          if (confirm === 'start') await api.startExperiment(e.id);
          else await api.setExperimentStatus(e.id, 'completed');
          state.reload();
        }}
      />
    </>
  );
}

export function Runs() {
  const [status, setStatus] = useState<RunStatus | ''>('');
  const state = useAsync(() => api.runs({ status: status || undefined, limit: '500' }), [status], 10_000);
  return (
    <>
      <PageHeader title="Runs">All recorded runs across experiments, including retries and failed or invalidated runs.</PageHeader>
      <label className="mb-3 block text-sm">
        <span className="mr-2 text-ink-soft">Status</span>
        <select className={`${inputClass} w-auto`} value={status} onChange={(ev) => setStatus(ev.target.value as RunStatus | '')}>
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s ? STATUS_LABEL[s] : 'All'}
            </option>
          ))}
        </select>
      </label>
      {state.error ? <ErrorBox error={state.error} onRetry={state.reload} /> : null}
      {!state.data ? <Loading label="Loading runs" /> : <RunTable runs={state.data.runs} showExperiment />}
    </>
  );
}
