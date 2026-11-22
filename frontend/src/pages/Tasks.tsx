import { useMemo, useState } from 'react';
import {
  Button,
  CopyButton,
  EmptyState,
  ErrorBox,
  Hash,
  Info,
  inputClass,
  Loading,
  PageHeader,
  Section,
  Table,
} from '../components/ui.tsx';
import { api } from '../lib/api.ts';
import { BenchmarkSwitch } from '../components/BenchmarkSwitch.tsx';
import { BENCHMARKS, bytes, CATEGORIES, categoriesFor, categoryLabel, dateTime, isSwebench, pct, taskBenchmark } from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { Task } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

export interface TaskFilters {
  benchmark?: string;
  q: string;
  category: string;
  difficulty: string;
  validation: string;
}

export function filterTasks(tasks: Task[], f: TaskFilters): Task[] {
  const q = f.q.trim().toLowerCase();
  return tasks.filter(
    (t) =>
      (!f.benchmark || taskBenchmark(t) === f.benchmark) &&
      (!f.category || t.category === f.category) &&
      (!f.difficulty || t.difficulty === f.difficulty) &&
      (!f.validation || t.validationStatus === f.validation) &&
      (!q || `${t.id} ${t.title} ${t.metadata.summary}`.toLowerCase().includes(q)),
  );
}

const VALIDATION_LABEL: Record<string, string> = {
  validated: 'Validated',
  stale: 'Stale (task changed)',
  failed: 'Validation failed',
  not_validated: 'Not validated',
  dataset_missing: 'Dataset not downloaded',
};

export function ValidationBadge({ status }: { status: string }) {
  const tone =
    status === 'validated'
      ? 'bg-pass-tint text-pass'
      : status === 'not_validated' || status === 'dataset_missing'
        ? 'bg-void-tint text-ink-soft'
        : 'bg-fail-tint text-fail';
  return <span className={`inline-block rounded-sm px-1.5 py-0.5 text-xs font-medium ${tone}`}>{VALIDATION_LABEL[status] ?? status}</span>;
}

export function TasksView({ tasks, initialBenchmark = '' }: { tasks: Task[]; initialBenchmark?: string }) {
  const [f, setF] = useState<TaskFilters>({ benchmark: initialBenchmark, q: '', category: '', difficulty: '', validation: '' });
  const counts = Object.fromEntries(BENCHMARKS.map((b) => [b.id, tasks.filter((t) => taskBenchmark(t) === b.id).length]));
  const swe = tasks.filter((t) => taskBenchmark(t) === 'swebench_verified');
  const sweMissing = swe.filter((t) => t.validationStatus === 'dataset_missing').length;
  const [sort, setSort] = useState<'id' | 'difficulty'>('id');
  const rows = useMemo(() => {
    const order = { easy: 0, medium: 1, hard: 2 } as Record<string, number>;
    const list = filterTasks(tasks, f);
    return sort === 'id' ? list : [...list].sort((a, b) => order[a.difficulty] - order[b.difficulty] || a.id.localeCompare(b.id));
  }, [tasks, f, sort]);
  return (
    <>
      <PageHeader
        title="Benchmark tasks"
        actions={
          <BenchmarkSwitch
            value={f.benchmark ?? ''}
            onChange={(b) => setF({ ...f, benchmark: b, category: '' })}
            counts={counts}
            allowAll
          />
        }
      >
        Three benchmarks. The <strong className="font-medium">custom suite</strong> has {counts.custom} synthetic Python tasks, three per
        category, scored by hidden tests that are never shown here or given to an assistant.{' '}
        <strong className="font-medium">SWE-bench Verified</strong> has {counts.swebench_verified} real GitHub issues, chosen from
        leaderboard difficulty tertiles and scored by the official SWE-bench harness.{' '}
        <strong className="font-medium">Golden</strong> has {counts.golden ?? 0} tasks from the golden dataset (golden/) in six domains (bug
        fix, feature, refactoring, performance, security fix, frontend/visual), from SWE-bench Verified, Multilingual, Multimodal and Pro,
        scored by hidden tests in Docker. Tasks marked <em>core</em> form a reviewed, domain-balanced set of 5 per domain.
      </PageHeader>
      {sweMissing && f.benchmark !== 'custom' ? (
        <div className="mb-4 rounded border border-pending/40 bg-pending-tint px-4 py-2.5 text-sm">
          {sweMissing} SWE-bench tasks are waiting for their issue text. Download the dataset once (free, needs Hugging Face access), then
          synchronise tasks:{' '}
          <code className="font-mono text-xs">python swebench_pilot/pilot.py select --ids-from swebench_pilot/candidates.json</code>
        </div>
      ) : null}
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Search</span>
          <input
            className={inputClass}
            value={f.q}
            placeholder="ID, title or summary"
            onChange={(e) => setF({ ...f, q: e.target.value })}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Category</span>
          <select className={inputClass} value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
            <option value="">All categories</option>
            {f.benchmark !== 'swebench_verified'
              ? (f.benchmark
                  ? categoriesFor(f.benchmark)
                  : [...CATEGORIES, ...categoriesFor('golden').filter((g) => !CATEGORIES.some((c) => c.id === g.id))]
                ).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))
              : null}
            {f.benchmark !== 'custom' ? <option value="swebench_verified">SWE-bench Verified</option> : null}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Difficulty</span>
          <select className={inputClass} value={f.difficulty} onChange={(e) => setF({ ...f, difficulty: e.target.value })}>
            <option value="">All difficulties</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">Validation</span>
          <select className={inputClass} value={f.validation} onChange={(e) => setF({ ...f, validation: e.target.value })}>
            <option value="">Any status</option>
            {Object.entries(VALIDATION_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No tasks match these filters">Clear a filter to see more tasks.</EmptyState>
      ) : (
        <Table caption="Benchmark tasks">
          <thead>
            <tr>
              <th>
                <button type="button" className="font-medium hover:text-action" onClick={() => setSort('id')} aria-pressed={sort === 'id'}>
                  ID
                </button>
              </th>
              <th>Title</th>
              <th>Category</th>
              <th>
                <button
                  type="button"
                  className="font-medium hover:text-action"
                  onClick={() => setSort('difficulty')}
                  aria-pressed={sort === 'difficulty'}
                >
                  Difficulty
                </button>
                <Info>
                  Custom suite: easy is one function or file, medium is several interacting rules, hard is a design-level or cross-module
                  change. SWE-bench: the tertile of how many of 122 leaderboard submissions resolved the issue (easy = most did).
                </Info>
              </th>
              <th className="text-right">
                Target tests
                <Info>Custom suite: hidden acceptance checks. SWE-bench: FAIL_TO_PASS tests the real fix made pass.</Info>
              </th>
              <th>Version</th>
              <th>Validation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="hover:bg-paper">
                <td className="font-mono text-xs">
                  <Link to={`/tasks/${t.id}`} className="text-action hover:underline">
                    {t.id}
                  </Link>
                </td>
                <td>
                  <Link to={`/tasks/${t.id}`} className="hover:underline">
                    {t.title}
                  </Link>
                  <div className="text-xs text-ink-faint">{t.metadata.summary}</div>
                </td>
                <td className="whitespace-nowrap">
                  {categoryLabel(t.category)}
                  {t.metadata.swebench ? <div className="text-xs text-ink-faint">{t.metadata.swebench.repo}</div> : null}
                </td>
                <td className="capitalize">{t.difficulty}</td>
                <td className="tabular text-right">
                  {isSwebench(t)
                    ? (t.metadata.swebench?.fail_to_pass_count ?? '—')
                    : (t.expectedAcceptanceTotal ?? t.metadata.acceptanceTests.length)}
                </td>
                <td className="whitespace-nowrap text-xs">{isSwebench(t) ? 'Verified' : `${t.version} / tests ${t.testVersion}`}</td>
                <td>
                  <ValidationBadge status={t.validationStatus} />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <p className="mt-2 text-xs text-ink-faint">
        {rows.length} of {tasks.length} tasks shown.
      </p>
    </>
  );
}

export function Tasks() {
  const state = useAsync(() => api.tasks(), []);
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Loading tasks" />;
  return <TasksView tasks={state.data.tasks} />;
}

export function TaskDetail({ id }: { id: string }) {
  const state = useAsync(() => api.task(id), [id]);
  const [file, setFile] = useState<{ path: string; content: string } | null>(null);
  const [fileError, setFileError] = useState<string>();
  if (state.error) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Loading task" />;
  const t = state.data.task;
  const m = t.metadata;
  if (isSwebench(t)) return <SwebenchTaskDetail t={t} />;
  return (
    <>
      <PageHeader
        title={`${t.id}: ${t.title}`}
        crumbs={[{ label: 'Benchmark tasks', to: '/tasks' }, { label: t.id }]}
        actions={<ValidationBadge status={t.validationStatus} />}
      >
        {categoryLabel(t.category)}, {t.difficulty}. {m.difficultyRationale}
      </PageHeader>

      {t.validationStatus !== 'validated' ? (
        <div className="mb-6 rounded border border-fail/40 bg-fail-tint px-4 py-2.5 text-sm">
          This task is not ready for official experiments: its validation is {t.validationStatus.replace('_', ' ')}. Run{' '}
          <code className="font-mono">python -m evaluator.cli validate --task {t.id}</code> and synchronise tasks.
        </div>
      ) : null}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          <Section title="Frozen assistant prompt" aside={<CopyButton text={t.prompt ?? ''} label="Copy prompt" />}>
            <pre className="whitespace-pre-wrap rounded border border-rule bg-panel p-4 font-sans text-sm leading-relaxed">{t.prompt}</pre>
          </Section>
          <Section title="Required behaviour">
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {m.requiredBehavior.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </Section>
          <Section title="Acceptance criteria">
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {m.acceptanceCriteria.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </Section>
          <Section title="Acceptance test summary" aside="Descriptions only; test code stays hidden">
            <Table caption="Acceptance tests">
              <thead>
                <tr>
                  <th>Check</th>
                  <th>What it verifies</th>
                </tr>
              </thead>
              <tbody>
                {m.acceptanceTests.map((a) => (
                  <tr key={a.id}>
                    <td className="font-mono text-xs">{a.id}</td>
                    <td>{a.description}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Section>
        </div>
        <div>
          <Section title="Starter files">
            <ul className="space-y-1 text-sm">
              {m.starterFiles.map((f) => (
                <li key={f.path} className="flex justify-between gap-2">
                  <button
                    type="button"
                    className="truncate text-left font-mono text-xs text-action hover:underline"
                    onClick={async () => {
                      setFileError(undefined);
                      try {
                        setFile(await api.starterFile(t.id, f.path));
                      } catch (e) {
                        setFileError((e as Error).message);
                      }
                    }}
                  >
                    {f.path}
                  </button>
                  <span className="text-xs text-ink-faint">{bytes(f.size)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-ink-faint">Location: {m.starterLocation}</p>
          </Section>
          <Section title="Constraints">
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-ink-soft">Time limit</dt>
                <dd>{m.timeLimitMinutes} minutes</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Files the assistant may change</dt>
                <dd className="font-mono text-xs">{m.scope.allowed_paths.join(', ')}</dd>
              </div>
              {m.scope.protected_paths.length ? (
                <div>
                  <dt className="text-ink-soft">Protected (restored before grading)</dt>
                  <dd className="font-mono text-xs">{m.scope.protected_paths.join(', ')}</dd>
                </div>
              ) : null}
              {m.testWriting ? (
                <div>
                  <dt className="text-ink-soft">Test-quality thresholds</dt>
                  <dd>
                    at least {String(m.testWriting.min_tests)} tests, {Number(m.testWriting.min_line_coverage) * 100}% line coverage,{' '}
                    {Number(m.testWriting.min_mutation_score) * 100}% of hidden mutants detected
                  </dd>
                </div>
              ) : null}
            </dl>
          </Section>
          <Section title="Version and integrity">
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Task version</dt>
                <dd>{t.version}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Test version</dt>
                <dd>{t.testVersion}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Task hash</dt>
                <dd>
                  <Hash value={t.taskHash} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Prompt hash</dt>
                <dd>
                  <Hash value={t.promptHash} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Test hash</dt>
                <dd>
                  <Hash value={t.testHash} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-soft">Validated</dt>
                <dd>{dateTime(t.validatedAt)}</dd>
              </div>
            </dl>
          </Section>
        </div>
      </div>
      {fileError ? <ErrorBox error={new Error(fileError)} /> : null}
      {file ? (
        <Section
          title={file.path}
          aside={
            <Button variant="quiet" onClick={() => setFile(null)}>
              Close
            </Button>
          }
        >
          <pre className="max-h-[32rem] overflow-auto rounded border border-rule bg-panel p-4 font-mono text-xs leading-relaxed">
            {file.content}
          </pre>
        </Section>
      ) : null}
    </>
  );
}

export function SwebenchTaskDetail({ t }: { t: Task }) {
  const sw = t.metadata.swebench;
  const ready = t.validationStatus === 'validated';
  return (
    <>
      <PageHeader
        title={t.title}
        crumbs={[{ label: 'Benchmark tasks', to: '/tasks' }, { label: t.id }]}
        actions={<ValidationBadge status={t.validationStatus} />}
      >
        {taskBenchmark(t) === 'golden'
          ? `Golden set (${sw?.harness === 'swebench_pro' ? 'SWE-bench Pro' : (sw?.dataset ?? '').split('/').pop()?.replace(/_/g, ' ')}${sw?.golden?.core ? ', balanced core' : ''})`
          : 'SWE-bench Verified'}
        , {t.difficulty}.{' '}
        {t.metadata.difficultyRationale}
      </PageHeader>
      {!ready ? (
        <div className="mb-6 rounded border border-pending/40 bg-pending-tint px-4 py-2.5 text-sm">
          The issue text and base commit come from the SWE-bench Verified dataset, which has not been downloaded on this machine. Run{' '}
          <code className="font-mono text-xs">python swebench_pilot/pilot.py select --ids-from swebench_pilot/candidates.json</code>, then
          synchronise tasks on the Dashboard. Until then the task cannot be added to an experiment.
        </div>
      ) : null}
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div>
          <Section
            title="Assistant prompt (issue text)"
            aside={ready ? <CopyButton text={t.prompt ?? ''} label="Copy prompt" /> : undefined}
          >
            <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap rounded border border-rule bg-panel p-4 font-sans text-sm leading-relaxed">
              {t.prompt}
            </pre>
          </Section>
          <Section title="How this task is scored">
            <ol className="list-decimal space-y-1.5 pl-5 text-sm">
              <li>
                Create workspace clones <span className="font-mono text-xs">{sw?.repo}</span> at the issue&apos;s base commit and saves the
                issue as ISSUE.md.
              </li>
              <li>The operator works the issue with the assistant and leaves the changes uncommitted.</li>
              <li>Submit turns every change into one patch (ISSUE.md excluded).</li>
              <li>
                The official SWE-bench harness applies the patch in the task&apos;s Docker image and runs the hidden tests: FAIL_TO_PASS (
                {sw?.fail_to_pass_count ?? 'the'} tests the real fix made pass) and PASS_TO_PASS ({sw?.pass_to_pass_count ?? 'the'} tests that
                already passed).
              </li>
              <li>
                The task counts as resolved only if all of them pass. A patch that does not apply, or no change at all, is unresolved.
              </li>
            </ol>
          </Section>
        </div>
        <div>
          <Section title="Task facts">
            <dl className="space-y-2 text-sm">
              {sw?.golden ? (
                <div>
                  <dt className="text-ink-soft">Golden domain</dt>
                  <dd>
                    {sw.golden.domain.replace(/_/g, ' ')}
                    {sw.golden.subdomain ? <span className="text-ink-faint"> / {sw.golden.subdomain.replace(/_/g, ' ')}</span> : null}
                    {sw.golden.gold_quality_score != null ? (
                      <div className="text-xs text-ink-faint">Reference patch QualityScore {sw.golden.gold_quality_score.toFixed(1)}</div>
                    ) : null}
                  </dd>
                </div>
              ) : null}
              <div>
                <dt className="text-ink-soft">Repository</dt>
                <dd className="font-mono text-xs">{sw?.repo}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Base commit</dt>
                <dd>{sw?.base_commit ? <Hash value={sw.base_commit} /> : 'from dataset'}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Leaderboard difficulty</dt>
                <dd>
                  {sw?.leaderboard_share != null ? `${pct(sw.leaderboard_share)} of submissions resolved it` : '—'} ({sw?.tier} tertile)
                </dd>
              </div>
              {sw?.dataset_difficulty ? (
                <div>
                  <dt className="text-ink-soft">Annotators&apos; time estimate</dt>
                  <dd>{sw.dataset_difficulty}</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-ink-soft">Time limit</dt>
                <dd>{t.metadata.timeLimitMinutes} minutes</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Dataset</dt>
                <dd className="font-mono text-xs">{sw?.dataset}</dd>
              </div>
              <div>
                <dt className="text-ink-soft">Task hash</dt>
                <dd>
                  <Hash value={t.taskHash} />
                </dd>
              </div>
            </dl>
          </Section>
        </div>
      </div>
    </>
  );
}
