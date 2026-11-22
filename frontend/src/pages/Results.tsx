import { useState } from 'react';
import { CountBars, RangeChart, SuccessChart } from '../components/charts.tsx';
import { EmptyState, ErrorBox, Info, inputClass, Loading, PageHeader, Section, Table } from '../components/ui.tsx';
import { api } from '../lib/api.ts';
import { BenchmarkSwitch } from '../components/BenchmarkSwitch.tsx';
import { ASSISTANTS, assistantName, categoriesFor, categoryLabel, duration, num, pct } from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { Experiment, Summary } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

export function ResultsView({ summary: s, records }: { summary: Summary; records: Record<string, any>[] }) {
  if (!s.hasData) {
    return (
      <EmptyState title="No experimental data yet">
        No run in this scope has completed evaluation, so there is nothing to compare. Planned attempts: {s.overall.planned}. Runs in
        progress: {s.overall.inProgress}. Operational failures: {s.overall.operationalFailures}.
      </EmptyState>
    );
  }
  const a = s.byAssistant;
  return (
    <>
      <Section
        title="Functional success by assistant"
        aside={
          <>
            Denominator: completed effective runs. Whiskers: Wilson 95% interval.
            <Info>
              Descriptive only. Intervals assume independent attempts, but attempts share tasks, so treat them as rough. Statistical tests
              are in analysis/analyze.py.
            </Info>
          </>
        }
      >
        <SuccessChart
          title="Success rate by assistant"
          data={a.map((x) => ({
            key: x.assistantId,
            label: assistantName(x.assistantId),
            rate: x.successRate,
            low: x.successCi95?.low ?? null,
            high: x.successCi95?.high ?? null,
            successes: x.successes,
            n: x.completed,
          }))}
        />
        {s.scope.benchmark === 'golden' ? (
          <div className="mt-4">
            <Table caption="Raw and domain-balanced success by assistant">
              <thead>
                <tr>
                  <th>Assistant</th>
                  <th className="text-right">Raw success</th>
                  <th className="text-right">Domain-balanced success</th>
                  <th className="text-right">Domains with runs</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {a.map((x) => (
                  <tr key={x.assistantId}>
                    <td>{assistantName(x.assistantId)}</td>
                    <td className="text-right">
                      {pct(x.successRate)} <span className="text-xs text-ink-faint">({x.successes}/{x.completed})</span>
                    </td>
                    <td className="text-right font-medium">{pct(x.domainBalanced?.rate)}</td>
                    <td className="text-right">
                      {x.domainBalanced ? `${x.domainBalanced.domains} of ${x.domainBalanced.of}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="mt-2 text-xs text-ink-faint">
              Domain-balanced success is the mean of the per-domain success rates, so each domain counts equally. Use it as the headline
              score for the golden set; it is only comparable between assistants that have runs in the same domains.
            </p>
          </div>
        ) : null}
      </Section>

      <Section
        title="Success by category and assistant"
        aside={
          s.scope.benchmark === 'swebench_verified'
            ? 'SWE-bench pilot: one category; see the per-run table for each issue'
            : s.scope.benchmark === 'golden'
              ? 'Golden set: categories are the dataset domains; compare domains, not just the overall rate'
              : 'Exploratory: each cell has at most 3 tasks × attempts'
        }
      >
        <Table caption="Success by category and assistant">
          <thead>
            <tr>
              <th>Category</th>
              {ASSISTANTS.map((x) => (
                <th key={x.id} className="text-right">
                  {x.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="tabular">
            {categoriesFor(s.scope.benchmark).map((c) => (
              <tr key={c.id}>
                <td>{c.label}</td>
                {ASSISTANTS.map((x) => {
                  const cell = s.byAssistantCategory.find((v) => v.category === c.id && v.assistantId === x.id);
                  return (
                    <td key={x.id} className="text-right">
                      {cell && cell.completed ? (
                        <>
                          {pct(cell.successRate)}{' '}
                          <span className="text-xs text-ink-faint">
                            ({cell.successes}/{cell.completed})
                          </span>
                        </>
                      ) : (
                        <span className="text-ink-faint">no data</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Session duration" aside="Wall-clock time from session start to end, completed runs only">
        <RangeChart
          title="Duration distribution by assistant"
          data={a.map((x) => ({
            key: x.assistantId,
            label: assistantName(x.assistantId),
            n: x.duration.n,
            min: x.duration.min,
            q1: x.duration.q1,
            median: x.duration.median,
            q3: x.duration.q3,
            max: x.duration.max,
          }))}
        />
        <p className="mt-1 text-xs text-ink-faint">Box: interquartile range. Line: median. Whiskers: minimum and maximum.</p>
      </Section>

      <div>
        <Section title="Mean iterations per run" aside="Prompts sent, including the first">
          <CountBars
            title="Mean iterations"
            data={a.map((x) => ({ key: x.assistantId, label: assistantName(x.assistantId), value: x.iterations.mean, n: x.iterations.n }))}
          />
        </Section>
        <Section title="Mean human interventions per run">
          <CountBars
            title="Mean human interventions"
            data={a.map((x) => ({
              key: x.assistantId,
              label: assistantName(x.assistantId),
              value: x.interventions.mean,
              n: x.interventions.n,
            }))}
          />
        </Section>
      </div>

      {s.scope.benchmark && s.scope.benchmark !== 'custom' && (
        <Section title="Code quality of the patches" aside="QualityScore 0–100; only problems the patch introduces count">
          <p className="mb-3 text-sm text-slate-600">
            Each submitted patch is scored with the golden Code Quality Module, the same scorer that rated every reference
            fix. Each problem it adds costs points: new lint findings, over-complex functions, a maintainability drop,
            security findings, debug or scratch leftovers, and bloat compared with the reference fix. 100 means
            nothing was found. The <em>resolved</em> column is the fairer comparison, because failed attempts are
            often small and look clean.
          </p>
          <Table caption="Patch code quality">
            <thead>
              <tr>
                <th>Assistant</th>
                <th className="text-right">Scored patches</th>
                <th className="text-right">Mean (all)</th>
                <th className="text-right">Mean (resolved)</th>
                <th className="text-right">vs reference fix</th>
                <th className="text-right">Reliability</th>
                <th className="text-right">Complexity</th>
                <th className="text-right">Maintainability</th>
                <th className="text-right">Security</th>
                <th className="text-right">Hygiene</th>
                <th className="text-right">Size</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {a.map((x) => {
                const q = x.quality;
                return (
                  <tr key={x.assistantId}>
                    <td>{assistantName(x.assistantId)}</td>
                    <td className="text-right">{q.n || (q.unavailable ? `unavailable (${q.unavailable})` : '—')}</td>
                    <td className="text-right">{q.n ? num(q.meanScore, 1) : '—'}</td>
                    <td className="text-right">{q.nResolved ? `${num(q.meanScoreResolved, 1)} (n=${q.nResolved})` : '—'}</td>
                    <td className="text-right">
                      {q.nWithGold && q.meanDeltaVsGold !== null
                        ? `${q.meanDeltaVsGold >= 0 ? '+' : ''}${num(q.meanDeltaVsGold, 1)} (ref ${num(q.meanGoldScore, 1)})`
                        : '—'}
                    </td>
                    {(['reliability', 'complexity', 'maintainability', 'security', 'hygiene', 'size'] as const).map((d) => (
                      <td key={d} className="text-right">
                        {q.n ? num(q.subscores[d], 0) : '—'}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Section>
      )}

      <Section title="Quality, security and regressions" aside="Counts over completed runs where the tool ran">
        <Table caption="Quality and security">
          <thead>
            <tr>
              <th>Assistant</th>
              <th className="text-right">Regression failures</th>
              <th className="text-right">Mean new Ruff findings</th>
              <th className="text-right">New Semgrep findings</th>
              <th className="text-right">Runs with new Semgrep findings</th>
              <th className="text-right">Changed files outside scope</th>
              <th className="text-right">Test-writing coverage / mutants</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {a.map((x) => (
              <tr key={x.assistantId}>
                <td>{assistantName(x.assistantId)}</td>
                <td className="text-right">{x.regressionDenominator ? `${x.regressionFailures} of ${x.regressionDenominator}` : '—'}</td>
                <td className="text-right">{x.ruff.n ? `${num(x.ruff.newMean, 2)} (n=${x.ruff.n})` : 'not run'}</td>
                <td className="text-right">{x.semgrep.n ? x.semgrep.newTotal : `unavailable (${x.semgrep.unavailable})`}</td>
                <td className="text-right">{x.semgrep.n ? `${x.semgrep.runsWithNewFindings} of ${x.semgrep.n}` : '—'}</td>
                <td className="text-right">{x.outOfScopeRuns}</td>
                <td className="text-right">
                  {x.testWriting.n ? `${pct(x.testWriting.meanCoverage)} / ${pct(x.testWriting.meanMutationScore)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Missing data and operational failures" aside="Excluded from success rates">
        <Table caption="Missing data">
          <thead>
            <tr>
              <th>Assistant</th>
              <th className="text-right">Planned</th>
              <th className="text-right">Completed</th>
              <th className="text-right">Not started</th>
              <th className="text-right">In progress</th>
              <th className="text-right">Operational failures</th>
              <th className="text-right">Invalidated</th>
              <th className="text-right">Over time limit</th>
              <th className="text-right">Retries</th>
            </tr>
          </thead>
          <tbody className="tabular">
            {a.map((x) => (
              <tr key={x.assistantId}>
                <td>{assistantName(x.assistantId)}</td>
                <td className="text-right">{x.planned}</td>
                <td className="text-right">{x.completed}</td>
                <td className="text-right">{x.notStarted}</td>
                <td className="text-right">{x.inProgress}</td>
                <td className="text-right">{x.operationalFailures}</td>
                <td className="text-right">{x.invalidated}</td>
                <td className="text-right">{x.timeouts}</td>
                <td className="text-right">{x.retries}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Individual runs" aside={`${records.filter((r) => r.eligible_for_success).length} completed effective runs`}>
        <Table caption="Completed runs">
          <thead>
            <tr>
              <th>Run</th>
              <th>Task</th>
              <th>Category</th>
              <th>Assistant</th>
              <th className="text-right">Attempt</th>
              <th>Result</th>
              <th className="text-right">Duration</th>
              <th className="text-right">Iterations</th>
            </tr>
          </thead>
          <tbody>
            {records
              .filter((r) => r.eligible_for_success)
              .map((r) => (
                <tr key={r.run_id}>
                  <td className="font-mono text-xs">
                    <Link to={`/runs/${r.run_id}`} className="text-action hover:underline">
                      {String(r.run_id).slice(0, 8)}
                    </Link>
                  </td>
                  <td className="font-mono text-xs">{r.task_id}</td>
                  <td>{categoryLabel(r.task_category)}</td>
                  <td>{assistantName(r.assistant_id)}</td>
                  <td className="tabular text-right">{r.attempt_number}</td>
                  <td className={r.success ? 'text-pass' : 'text-fail'}>
                    {r.success ? 'Passed' : (r.outcome ?? 'Did not pass').replace(/_/g, ' ')}
                  </td>
                  <td className="tabular text-right">{duration(r.wall_clock_seconds)}</td>
                  <td className="tabular text-right">{num(r.iterations)}</td>
                </tr>
              ))}
          </tbody>
        </Table>
      </Section>

      <Section title="Caveats">
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">
          {s.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function Results() {
  const experiments = useAsync(() => api.experiments(), []);
  const [experimentId, setExperimentId] = useState('');
  const [benchmark, setBenchmark] = useState('custom');
  const state = useAsync(
    async () => {
      const [summary, records] = await Promise.all([
        api.summary(experimentId || undefined, benchmark),
        api.records(experimentId || undefined, benchmark),
      ]);
      return { summary, records: records.records };
    },
    [experimentId, benchmark],
    15_000,
  );
  return (
    <>
      <PageHeader title="Results comparison" actions={<BenchmarkSwitch value={benchmark} onChange={setBenchmark} />}>
        Measured outcomes from completed evaluations. Planned and unfinished attempts are reported as missing data, never as failures or
        successes. Custom-suite and SWE-bench results are shown separately: switch benchmark above.
      </PageHeader>
      <label className="mb-6 block max-w-md text-sm">
        <span className="mb-1 block font-medium">Scope</span>
        <select className={inputClass} value={experimentId} onChange={(e) => setExperimentId(e.target.value)}>
          <option value="">All experiments</option>
          {experiments.data?.experiments.map((e: Experiment) => (
            <option key={e.id} value={e.id}>
              {e.name} ({e.status})
            </option>
          ))}
        </select>
      </label>
      {state.error ? <ErrorBox error={state.error} onRetry={state.reload} /> : null}
      {!state.data ? <Loading label="Loading results" /> : <ResultsView summary={state.data.summary} records={state.data.records} />}
    </>
  );
}
