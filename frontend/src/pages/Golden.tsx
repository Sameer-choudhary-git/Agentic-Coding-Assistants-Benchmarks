import { ErrorBox, Loading, Notice, PageHeader, Section, Stat, Table } from '../components/ui.tsx';
import { api, goldenFigureUrl } from '../lib/api.ts';
import { dateTime, num, pct } from '../lib/format.ts';
import { Link } from '../lib/router.tsx';
import type { GoldenOverview } from '../lib/types.ts';
import { useAsync } from '../lib/useAsync.ts';

const DOMAIN_LABEL: Record<string, string> = {
  bug_fix: 'Bug fix',
  feature_implementation: 'Feature implementation',
  refactoring: 'Refactoring',
  performance: 'Performance',
  security_fix: 'Security fix',
  frontend_visual: 'Frontend / visual',
  test_generation: 'Test generation',
  offensive_security_ctf: 'Offensive security (CTF)',
};
const SOURCE_LABEL: Record<string, string> = {
  swebench_verified: 'SWE-bench Verified',
  swebench_plus: 'SWE-bench+',
  swebench_plusplus: 'SWE-Bench++',
  swebench_pro: 'SWE-bench Pro',
  swebench_multimodal: 'SWE-bench Multimodal',
  swebench_multilingual: 'SWE-bench Multilingual',
  swe_rebench: 'SWE-rebench',
  nyu_ctf: 'NYU CTF Bench (EnIGMA)',
};
const FIGURE_CAPTION: Record<string, string> = {
  'fig1_composition.png': 'Dataset composition by domain and source',
  'fig2_domain_heatmap.png': 'Resolve rate by agent and domain',
  'fig2b_repo_heatmap.png': 'Resolve rate by agent and repository',
  'fig3_difficulty_heatmap.png': 'Resolve rate by agent and difficulty',
  'fig4_quality.png': 'Patch quality of resolved and unresolved patches',
};
const DIFFS = ['easy', 'medium', 'hard'];
const sorted = (o: Record<string, number>) => Object.entries(o).sort((a, b) => b[1] - a[1]);

export function GoldenView({ g }: { g: GoldenOverview }) {
  const s = g.summary;
  const r = g.results;
  const agents = r ? [...r.agents].sort((a, b) => (r.overall[b]?.pool ?? 0) - (r.overall[a]?.pool ?? 0)) : [];
  const cal = g.difficultyCalibration;
  return (
    <>
      <PageHeader title="Golden dataset">
        {g.name} v{g.version}: {g.nTasks} tasks in {Object.keys(s.by_domain).length} domains, drawn from{' '}
        {Object.keys(s.by_source).length} public benchmarks after automatic quality gates. Built {dateTime(g.builtAt)} with seed {g.seed}.
        The agent results below are re-analyses of <em>published</em> runs, not runs recorded on this platform. Run your own on the{' '}
        <Link to="/tasks" className="text-action hover:underline">
          Golden benchmark
        </Link>
        .
      </PageHeader>

      <Section title="At a glance">
        <dl className="flex flex-wrap gap-x-10 gap-y-4">
          <Stat label="Golden tasks" value={g.nTasks} note={`${Object.keys(s.by_domain).length} domains`} />
          <Stat
            label="Candidate pool"
            value={s.pool_size.toLocaleString('en-US')}
            note={`${s.pool_admitted.toLocaleString('en-US')} passed the quality gates`}
          />
          <Stat label="Repositories" value={s.repos ?? '—'} note={`${Object.keys(s.by_language).length} languages`} />
          <Stat
            label="Runnable in this app"
            value={g.appTasks}
            note={`${Object.keys(g.appByDomain).length} domains; balanced core ${Object.values(g.appCoreByDomain).reduce((x, y) => x + y, 0)}`}
          />
          <Stat label="Reference-fix quality" value={num(s.gold_quality_mean ?? null)} note="mean QualityScore, 0–100" />
        </dl>
      </Section>

      <Section title="Runnable in this app" aside="Golden tasks the app can score with hidden tests in Docker">
        <Table caption="Runnable golden tasks by domain">
          <thead>
            <tr>
              <th scope="col">Domain</th>
              <th scope="col" className="text-right">
                Runnable tasks
              </th>
              <th scope="col" className="text-right">
                Balanced core
              </th>
            </tr>
          </thead>
          <tbody className="tabular">
            {sorted(g.appByDomain).map(([dom, n]) => (
              <tr key={dom}>
                <th scope="row" className="font-normal text-ink">
                  {DOMAIN_LABEL[dom] ?? dom}
                </th>
                <td className="text-right">{n}</td>
                <td className="text-right font-medium">{g.appCoreByDomain[dom] ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </Table>
        <p className="mt-2 text-xs text-ink-faint">
          Sources:{' '}
          {sorted(g.appBySource)
            .map(([src, n]) => `${SOURCE_LABEL[src] ?? src} ${n}`)
            .join(', ')}
          . The balanced core (seeded, spread over difficulty, source and repository) is the default selection for a Golden experiment, and
          Results reports a domain-balanced success rate so bug fixes cannot dominate the headline score. CTF and test-generation tasks
          need other judges and are not run in the app.
        </p>
      </Section>

      <Section title="Tasks by domain and difficulty" aside="Difficulty is calibrated on patch complexity">
        <Table caption="Golden tasks by domain and difficulty">
          <thead>
            <tr>
              <th scope="col">Domain</th>
              {DIFFS.map((d) => (
                <th key={d} scope="col" className="text-right capitalize">
                  {d}
                </th>
              ))}
              <th scope="col" className="text-right">
                Total
              </th>
            </tr>
          </thead>
          <tbody className="tabular">
            {sorted(s.by_domain).map(([dom, n]) => (
              <tr key={dom}>
                <th scope="row" className="font-normal text-ink">
                  {DOMAIN_LABEL[dom] ?? dom}
                </th>
                {DIFFS.map((d) => (
                  <td key={d} className="text-right">
                    {s.by_domain_difficulty[`${dom}|${d}`] ?? 0}
                  </td>
                ))}
                <td className="text-right font-medium">{n}</td>
              </tr>
            ))}
          </tbody>
        </Table>
        {cal ? (
          <p className="mt-2 text-xs text-ink-faint">
            Difficulty thresholds were fitted to {cal.n} human time estimates: balanced accuracy {pct(cal.balanced_accuracy)}, within one
            level {pct(cal.within_one)}, Spearman ρ {num(cal.spearman_rho, 2)}.
          </p>
        ) : null}
      </Section>

      <Section title="Sources and quality gates" aside="Gates: solution leaked in the issue, weak tests, duplicates, oversized patches">
        <Table caption="Sources, gate outcomes and tasks used">
          <thead>
            <tr>
              <th scope="col">Source</th>
              <th scope="col" className="text-right">
                Candidates
              </th>
              <th scope="col" className="text-right">
                Passed gates
              </th>
              <th scope="col" className="text-right">
                In golden set
              </th>
            </tr>
          </thead>
          <tbody className="tabular">
            {Object.entries(g.gateStats)
              .sort((a, b) => (s.by_source[b[0]] ?? 0) - (s.by_source[a[0]] ?? 0))
              .map(([src, st]) => (
                <tr key={src}>
                  <th scope="row" className="font-normal text-ink">
                    {SOURCE_LABEL[src] ?? src}
                  </th>
                  <td className="text-right">{(st.total ?? 0).toLocaleString('en-US')}</td>
                  <td className="text-right">
                    {(st.admitted ?? 0).toLocaleString('en-US')}{' '}
                    <span className="text-xs text-ink-faint">({pct(st.total ? (st.admitted ?? 0) / st.total : null)})</span>
                  </td>
                  <td className="text-right font-medium">{s.by_source[src] ?? 0}</td>
                </tr>
              ))}
          </tbody>
        </Table>
        <p className="mt-2 text-xs text-ink-faint">
          SWE-bench+ shows a low pass rate because most of its instances duplicate SWE-bench Verified, which is used instead.
        </p>
      </Section>

      {r ? (
        <Section title="Published agents on SWE-bench Verified" aside="Re-analysis of public leaderboard runs">
          <Table caption="Published agent results">
            <thead>
              <tr>
                <th scope="col">Agent</th>
                <th scope="col" className="text-right">
                  Resolved (pool)
                </th>
                <th scope="col" className="text-right">
                  Resolved (golden)
                </th>
                {DIFFS.map((d) => (
                  <th key={d} scope="col" className="text-right capitalize">
                    {d}
                  </th>
                ))}
                <th scope="col" className="text-right">
                  Repo gap
                </th>
                <th scope="col" className="text-right">
                  Quality-adjusted
                </th>
                <th scope="col" className="text-right">
                  Size vs. fix
                </th>
              </tr>
            </thead>
            <tbody className="tabular">
              {agents.map((a) => {
                const q = r.quality[a];
                return (
                  <tr key={a}>
                    <th scope="row" className="whitespace-nowrap font-normal text-ink">
                      {a}
                    </th>
                    <td className="text-right font-medium">{pct(r.overall[a]?.pool, 1)}</td>
                    <td className="text-right">{pct(r.overall[a]?.golden, 1)}</td>
                    {DIFFS.map((d) => (
                      <td key={d} className="text-right">
                        {pct(r.by_difficulty[a]?.[d])}
                      </td>
                    ))}
                    <td className="whitespace-nowrap text-right">{r.by_repo[a] ? `${num(r.by_repo[a].repo_gap_pp, 0)} pp` : '—'}</td>
                    <td className="text-right">{pct(q?.quality_adjusted, 1)}</td>
                    <td className="text-right">{q?.size_ratio_median != null ? `${num(q.size_ratio_median, 2)}×` : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-ink-faint">
            <li>
              Pool = all SWE-bench Verified tasks that passed the gates; golden = the golden set&apos;s Verified
              subset. Repo gap = best minus worst repository, in percentage points.
            </li>
            <li>
              Quality-adjusted counts a task only if it is resolved and its patch scores at least 80 on the QualityScore (lint, complexity,
              maintainability, security, leftovers, size).
            </li>
            {r.rank_tau != null ? (
              <li>
                Ranking by raw vs. quality-adjusted resolve rate agrees closely (Kendall τ = {num(r.rank_tau, 2)}).
                {r.top2_diff
                  ? ` The top two (${r.top2_diff.a}, ${r.top2_diff.b}) differ by ${num(r.top2_diff.diff * 100, 1)} pp, 95% CI ${num(
                      r.top2_diff.lo * 100,
                      1,
                    )} to ${num(r.top2_diff.hi * 100, 1)} pp${r.top2_diff.lo < 0 ? ', so they are not distinguishable' : ''}.`
                  : ''}
              </li>
            ) : null}
          </ul>
        </Section>
      ) : (
        <Notice>No published-agent results yet. Run `python -m agentbench evaluate --published` and `report` in golden/.</Notice>
      )}

      {g.figures.length ? (
        <Section title="Figures" aside="From golden/reports/figures">
          <div className="grid gap-6 xl:grid-cols-2">
            {g.figures.map((f) => (
              <figure key={f} className="rounded border border-rule bg-panel p-3">
                <a href={goldenFigureUrl(f)} target="_blank" rel="noreferrer">
                  <img src={goldenFigureUrl(f)} alt={FIGURE_CAPTION[f] ?? f} className="w-full" loading="lazy" />
                </a>
                <figcaption className="mt-2 text-sm text-ink-soft">{FIGURE_CAPTION[f] ?? f}</figcaption>
              </figure>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="Files">
        <ul className="space-y-1 text-sm">
          <li>
            <code className="font-mono text-xs">golden/dataset/golden_v{g.version}.jsonl</code> (and <code className="font-mono text-xs">.parquet</code>,{' '}
            <code className="font-mono text-xs">by_domain/</code>): the dataset
          </li>
          <li>
            <code className="font-mono text-xs">golden/dataset/DATASHEET.md</code>, <code className="font-mono text-xs">review_sheet.csv</code>:
            documentation and the human review sheet
          </li>
          <li>
            <code className="font-mono text-xs">golden/reports/RESEARCH_REPORT.md</code>, <code className="font-mono text-xs">RESULTS.md</code>: the
            write-up and full tables
          </li>
        </ul>
      </Section>
    </>
  );
}

export function Golden() {
  const { data, error, loading, reload } = useAsync(() => api.golden(), []);
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (loading || !data) return <Loading label="Loading golden dataset" />;
  return <GoldenView g={data} />;
}
