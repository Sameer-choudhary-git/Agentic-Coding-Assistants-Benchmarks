import { SuccessChart } from '../components/charts.tsx';
import { ExperimentMatrix } from '../components/Matrix.tsx';
import { EmptyState, ErrorBox, Info, Loading, PageHeader, Section, Stat, Table } from '../components/ui.tsx';
import { api } from '../lib/api.ts';
import { useState } from 'react';
import { BenchmarkSwitch } from '../components/BenchmarkSwitch.tsx';
import {
  assistantName,
  benchmarkLabel,
  byCategoryOrder,
  categoryLabel,
  dateTime,
  duration,
  num,
  pct,
  taskBenchmark,
} from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { EventItem, Experiment, PlannedAttempt, Run, Summary } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

const EVENT_TEXT: Record<string, string> = {
  experiment_created: 'Experiment created',
  experiment_started: 'Experiment started',
  workspace_prepared: 'Workspace prepared',
  run_started: 'Run started',
  run_stopped: 'Session stopped',
  run_submitted: 'Result submitted',
  evaluation_queued: 'Evaluation queued',
  evaluation_completed: 'Evaluation completed',
  evaluation_error: 'Evaluation failed',
  run_failed: 'Run marked as failed',
  run_invalidated: 'Run invalidated',
  run_retried: 'Retry created',
  run_labelled: 'Failure modes labelled',
  adapter_started: 'Adapter started',
  adapter_finished: 'Adapter finished',
  adapter_failed: 'Adapter failed',
  bundle_imported: 'Bundle imported',
  logged_iteration: 'Iteration logged',
  logged_intervention: 'Intervention logged',
};

export interface DashboardData {
  summary: Summary;
  events: EventItem[];
  focus: { experiment: Experiment; planned: PlannedAttempt[]; runs: Run[] } | null;
}

/** Pure view: renders only what the stored records contain. */
export function DashboardView({ data, controls }: { data: DashboardData; controls?: React.ReactNode }) {
  const { summary: s, events, focus } = data;
  const o = s.overall;
  return (
    <>
      <PageHeader title="Dashboard" actions={controls}>
        Planned work, recorded runs and measured outcomes for {benchmarkLabel(s.scope.benchmark)}. Every figure is computed from stored run
        and evaluation records; the two benchmarks are never pooled here.
      </PageHeader>

      <Section title="Study design and progress">
        <dl className="grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Benchmark tasks" value={s.totals.tasks} note={`${s.totals.validatedTasks} validated`} />
          <Stat label="Assistants" value={s.totals.assistants} />
          <Stat
            label="Planned attempts"
            value={s.totals.plannedAttempts}
            note={`${s.totals.experiments} experiment${s.totals.experiments === 1 ? '' : 's'}`}
          />
          <Stat label="Completed attempts" value={o.completed} note="evaluated, effective runs" />
          <Stat
            label="Failed or invalid"
            value={o.operationalFailures + o.invalidated}
            note={`${o.operationalFailures} operational, ${o.invalidated} invalidated`}
          />
          <Stat label="In progress" value={o.inProgress} note={`${o.notStarted} not started`} />
        </dl>
      </Section>

      {!s.hasData ? (
        <Section title="Measured results">
          <EmptyState title="No experimental data yet">
            Success rates, durations and findings appear here after the first run has been evaluated. Create an experiment on the{' '}
            <Link to="/experiments/new" className="text-action underline">
              new experiment
            </Link>{' '}
            page and complete a run to get started.
          </EmptyState>
        </Section>
      ) : (
        <>
          <Section
            title="Task success by assistant"
            aside={
              <>
                Bars: completed effective runs that passed. Whiskers: Wilson 95% interval.
                <Info>
                  Success rate = runs that passed all hidden acceptance checks with no regression failures and within the time limit,
                  divided by runs whose evaluation completed. Operational failures and invalidated runs are excluded and listed separately.
                </Info>
              </>
            }
          >
            <dl className="mb-4 flex flex-wrap gap-x-10 gap-y-3">
              <Stat label="Overall measured success" value={pct(o.successRate)} note={`${o.successes} of ${o.completed} completed runs`} />
              <Stat label="Median session duration" value={duration(o.duration.median)} note={`n = ${o.duration.n}`} />
              <Stat label="Mean iterations" value={num(o.iterations.mean)} note={`n = ${o.iterations.n}`} />
              <Stat label="Mean human interventions" value={num(o.interventions.mean)} note={`n = ${o.interventions.n}`} />
            </dl>
            <SuccessChart
              title="Task success rate by assistant"
              data={s.byAssistant.map((a) => ({
                key: a.assistantId,
                label: assistantName(a.assistantId),
                rate: a.successRate,
                low: a.successCi95?.low ?? null,
                high: a.successCi95?.high ?? null,
                successes: a.successes,
                n: a.completed,
              }))}
            />
          </Section>
          <Section title="Results by task category" aside="Exploratory: three tasks per category">
            <Table caption="Results by task category">
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="text-right">Planned</th>
                  <th className="text-right">Completed</th>
                  <th className="text-right">Passed</th>
                  <th className="text-right">Success rate</th>
                  <th className="text-right">Median duration</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {byCategoryOrder(s.byCategory).map((c) => (
                  <tr key={c.category}>
                    <td>{categoryLabel(c.category)}</td>
                    <td className="text-right">{c.planned}</td>
                    <td className="text-right">{c.completed}</td>
                    <td className="text-right">{c.successes}</td>
                    <td className="text-right">{pct(c.successRate)}</td>
                    <td className="text-right">{duration(c.duration.median)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Section>
        </>
      )}

      {focus ? (
        <Section
          title={`Experiment matrix: ${focus.experiment.name}`}
          aside={
            <Link to={`/experiments/${focus.experiment.id}`} className="text-action hover:underline">
              Open experiment monitor
            </Link>
          }
        >
          <ExperimentMatrix planned={focus.planned} runs={focus.runs} compact />
        </Section>
      ) : null}

      <Section title="Recent activity">
        {events.length === 0 ? (
          <EmptyState title="Nothing has happened yet">
            Activity is recorded when experiments are created and runs move through their lifecycle.
          </EmptyState>
        ) : (
          <ol className="divide-y divide-rule rounded border border-rule bg-panel text-sm">
            {events.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2">
                <span>
                  {EVENT_TEXT[e.type] ?? e.type}
                  {e.runId ? (
                    <>
                      {' '}
                      <Link to={`/runs/${e.runId}`} className="font-mono text-xs text-action hover:underline">
                        run {e.runId.slice(0, 8)}
                      </Link>
                    </>
                  ) : null}
                  {e.toStatus ? <span className="text-ink-faint"> now {e.toStatus.replace('_', ' ')}</span> : null}
                </span>
                <span className="text-xs text-ink-faint">
                  {dateTime(e.createdAt)} by {e.actor}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </>
  );
}

export function Dashboard() {
  const [benchmark, setBenchmark] = useState('custom');
  const state = useAsync<DashboardData>(
    async () => {
      const [summary, events, experiments, tasks] = await Promise.all([
        api.summary(undefined, benchmark),
        api.events(12),
        api.experiments(),
        api.tasks(),
      ]);
      const benchTasks = new Set(tasks.tasks.filter((t) => taskBenchmark(t) === benchmark).map((t) => t.id));
      const mine = experiments.experiments.filter((e) =>
        ((e.config.tasks as { id: string }[] | undefined) ?? []).some((t) => benchTasks.has(t.id)),
      );
      const active = mine.find((e) => e.status === 'active') ?? mine[0];
      let focus: DashboardData['focus'] = null;
      if (active) {
        const d = await api.experiment(active.id);
        focus = { experiment: d.experiment, planned: d.plannedAttempts, runs: d.runs };
      }
      return { summary, events: events.events, focus };
    },
    [benchmark],
    10_000,
  );
  if (state.error && !state.data) return <ErrorBox error={state.error} onRetry={state.reload} />;
  if (!state.data) return <Loading label="Loading dashboard" />;
  return <DashboardView data={state.data} controls={<BenchmarkSwitch value={benchmark} onChange={setBenchmark} />} />;
}
