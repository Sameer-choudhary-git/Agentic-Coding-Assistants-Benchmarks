/**
 * Component and view tests. Views are rendered to static HTML with react-dom/server, so the tests
 * need no browser or DOM emulation and run on any machine with Node.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { SuccessChart } from '../src/components/charts.tsx';
import { cellState, ExperimentMatrix } from '../src/components/Matrix.tsx';
import { StatusBadge } from '../src/components/ui.tsx';
import { axisDuration, categoryLabel, duration, num, pct, plannedAttemptCount, taskBenchmark } from '../src/lib/format.ts';
import { matchRoute, RouterProvider } from '../src/lib/router.tsx';
import type { Aggregate, PlannedAttempt, Run, Summary, Task } from '../src/lib/types.ts';
import { DashboardView } from '../src/pages/Dashboard.tsx';
import { ResultsView } from '../src/pages/Results.tsx';
import { EvidenceView, filterEvidence, formatEvidenceValue } from '../src/pages/Evidence.tsx';
import { filterTasks, SwebenchTaskDetail, TasksView } from '../src/pages/Tasks.tsx';
import { BenchmarkSwitch } from '../src/components/BenchmarkSwitch.tsx';

const render = (node: React.ReactNode) => renderToStaticMarkup(<RouterProvider initialPath="/">{node}</RouterProvider>);
const text = (html: string) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

const ASSISTANT_IDS = ['copilot', 'cursor', 'claude_code', 'codex'];
const CATEGORY_IDS = [
  'bug_fixing',
  'feature_implementation',
  'security_remediation',
  'refactoring',
  'test_writing',
  'repository_reasoning',
];

function agg(over: Partial<Aggregate> = {}): Aggregate {
  return {
    planned: 0,
    completed: 0,
    successes: 0,
    successRate: null,
    successCi95: null,
    intentToTreatRate: null,
    notStarted: 0,
    inProgress: 0,
    operationalFailures: 0,
    invalidated: 0,
    timeouts: 0,
    retries: 0,
    regressionFailures: 0,
    regressionDenominator: 0,
    duration: { n: 0, mean: null, median: null, q1: null, q3: null, min: null, max: null },
    iterations: { n: 0, mean: null, median: null },
    interventions: { n: 0, mean: null, median: null },
    ruff: { n: 0, unavailable: 0, newMean: null, newTotal: 0 },
    semgrep: { n: 0, unavailable: 0, newTotal: 0, runsWithNewFindings: 0, resolvedTotal: 0 },
    testWriting: { n: 0, meanCoverage: null, meanMutationScore: null },
    outOfScopeRuns: 0,
    quality: {
      n: 0,
      unavailable: 0,
      meanScore: null,
      medianScore: null,
      nResolved: 0,
      meanScoreResolved: null,
      nWithGold: 0,
      meanGoldScore: null,
      meanDeltaVsGold: null,
      subscores: { reliability: null, complexity: null, maintainability: null, security: null, hygiene: null, size: null },
    },
    ...over,
  };
}

function summary(hasData: boolean, assistantOver: Partial<Aggregate> = {}): Summary {
  return {
    scope: { experimentId: null, experiments: 1 },
    hasData,
    generatedAt: '2026-11-05T00:00:00Z',
    totals: { tasks: 18, validatedTasks: 18, assistants: 4, experiments: 1, plannedAttempts: 144, runsRecorded: hasData ? 4 : 0 },
    overall: agg(
      hasData ? { planned: 144, completed: 4, successes: 3, successRate: 0.75, notStarted: 140 } : { planned: 144, notStarted: 144 },
    ),
    byAssistant: ASSISTANT_IDS.map((id) => ({
      assistantId: id,
      name: id,
      ...agg({ planned: 36, ...(id === 'codex' ? assistantOver : {}) }),
    })),
    byCategory: CATEGORY_IDS.map((c) => ({ category: c, ...agg({ planned: 24 }) })),
    byAssistantCategory: [],
    caveats: ['Category-level results are exploratory.'],
  };
}

describe('format helpers', () => {
  it('computes the planned attempt formula', () => {
    assert.equal(plannedAttemptCount(18, 4, 2), 144);
    assert.equal(plannedAttemptCount(0, 4, 2), 0);
  });
  it('renders missing values as a dash, never as zero', () => {
    assert.equal(pct(null), '—');
    assert.equal(num(undefined), '—');
    assert.equal(duration(null), '—');
    assert.equal(pct(0.5), '50%');
    assert.equal(duration(125), '2 min 05 s');
    assert.equal(axisDuration(30, 60), '30 s');
    assert.equal(axisDuration(600, 1200), '10 min');
  });
});

describe('router', () => {
  it('matches parameterised routes', () => {
    assert.deepEqual(matchRoute('/runs/:id', '/runs/abc?x=1'), { id: 'abc' });
    assert.equal(matchRoute('/runs/:id', '/runs'), null);
    assert.deepEqual(matchRoute('/', '/'), {});
  });
});

describe('dashboard', () => {
  it('shows "No experimental data yet" and no percentages on an empty database', () => {
    const html = render(<DashboardView data={{ summary: summary(false), events: [], focus: null }} />);
    const t = text(html);
    assert.match(t, /No experimental data yet/);
    assert.doesNotMatch(t, /\d+%/, 'no success rate may be displayed without data');
    assert.match(t, /Planned attempts 144/);
    assert.match(t, /Completed attempts 0/);
  });
  it('shows measured success computed from stored records', () => {
    const html = render(
      <DashboardView data={{ summary: summary(true, { completed: 4, successes: 3, successRate: 0.75 }), events: [], focus: null }} />,
    );
    const t = text(html);
    assert.match(t, /Overall measured success 75%/);
    assert.match(t, /3 of 4 completed runs/);
    assert.match(t, /75% \(3\/4\)/);
    assert.match(t, /no completed runs/, 'assistants without data are labelled, not drawn as 0%');
  });
});

describe('results comparison', () => {
  it('shows patch code quality for harness benchmarks only, with resolved-only and reference columns', () => {
    const quality = {
      n: 4,
      unavailable: 0,
      meanScore: 88.5,
      medianScore: 90,
      nResolved: 3,
      meanScoreResolved: 91.2,
      nWithGold: 4,
      meanGoldScore: 95,
      meanDeltaVsGold: -6.5,
      subscores: { reliability: 90, complexity: 100, maintainability: 100, security: 100, hygiene: 70, size: 100 },
    };
    const golden = { ...summary(true, { completed: 4, successes: 3, successRate: 0.75, quality }), scope: { experimentId: null, benchmark: 'golden' } };
    const t = text(render(<ResultsView summary={golden} records={[]} />));
    assert.match(t, /Code quality of the patches/);
    assert.match(t, /91\.2 \(n=3\)/);
    assert.match(t, /-6\.5 \(ref 95\)/);
    const custom = text(render(<ResultsView summary={summary(true, { completed: 4, successes: 3, successRate: 0.75 })} records={[]} />));
    assert.doesNotMatch(custom, /Code quality of the patches/);
  });
  it('renders an empty state instead of charts when there is no data', () => {
    const t = text(render(<ResultsView summary={summary(false)} records={[]} />));
    assert.match(t, /No experimental data yet/);
    assert.doesNotMatch(t, /Functional success by assistant/);
  });
  it('labels denominators and exploratory category results', () => {
    const t = text(render(<ResultsView summary={summary(true, { completed: 4, successes: 3, successRate: 0.75 })} records={[]} />));
    assert.match(t, /Denominator: completed effective runs/);
    assert.match(t, /Exploratory/);
    assert.match(t, /Missing data and operational failures/);
  });
});

describe('charts', () => {
  it('draws null rates as "no completed runs" with their sample size', () => {
    const html = render(
      <SuccessChart
        title="t"
        data={[
          { key: 'copilot', label: 'Copilot', rate: null, low: null, high: null, successes: 0, n: 0 },
          { key: 'codex', label: 'Codex', rate: 0.5, low: 0.1, high: 0.9, successes: 1, n: 2 },
        ]}
      />,
    );
    assert.match(html, /no completed runs/);
    assert.match(html, /50% \(1\/2\)/);
    assert.equal((html.match(/<rect/g) ?? []).length, 1);
  });
});

describe('experiment matrix', () => {
  it('renders one cell per planned attempt and reflects run state', () => {
    const planned: PlannedAttempt[] = [];
    let seq = 0;
    for (let t = 1; t <= 18; t += 1)
      for (const a of ASSISTANT_IDS)
        for (const n of [1, 2])
          planned.push({
            id: `p${seq}`,
            taskId: `T-${String(t).padStart(2, '0')}`,
            assistantId: a,
            attemptNumber: n,
            sequence: ++seq,
            timeLimitSeconds: 1200,
          });
    const run = { id: 'r1', plannedAttemptId: 'p0', runNumber: 1, status: 'completed', success: true } as Run;
    const html = render(<ExperimentMatrix planned={planned} runs={[run]} />);
    assert.equal((html.match(/rounded-\[2px\] border/g) ?? []).length - 7, 144, '144 cells plus 7 legend swatches');
    assert.match(html, /href="\/runs\/r1"/);
    assert.equal(cellState(undefined), 'not_started');
    assert.equal(cellState({ ...run, success: false } as Run), 'not_passed');
    assert.equal(cellState({ ...run, status: 'failed' } as Run), 'failed');
    assert.equal(cellState({ ...run, status: 'evaluating' } as Run), 'in_progress');
  });
});

describe('task explorer', () => {
  const tasks = Array.from({ length: 18 }, (_, i) => ({
    id: `T-${i}`,
    title: `Task ${i}`,
    category: CATEGORY_IDS[i % 6],
    difficulty: ['easy', 'medium', 'hard'][i % 3],
    kind: 'standard',
    version: '1.0.0',
    testVersion: '1.0.0',
    taskHash: 'h',
    promptHash: 'p',
    testHash: 't',
    starterHash: 's',
    validationStatus: i === 0 ? 'stale' : 'validated',
    validatedAt: null,
    expectedAcceptanceTotal: 5,
    metadata: { summary: `summary ${i}`, acceptanceTests: [], starterFiles: [] },
  })) as unknown as Task[];
  it('filters by category, difficulty, validation and search text', () => {
    assert.equal(filterTasks(tasks, { q: '', category: '', difficulty: '', validation: '' }).length, 18);
    assert.equal(filterTasks(tasks, { q: '', category: 'refactoring', difficulty: '', validation: '' }).length, 3);
    assert.equal(filterTasks(tasks, { q: '', category: '', difficulty: 'hard', validation: '' }).length, 6);
    assert.equal(filterTasks(tasks, { q: '', category: '', difficulty: '', validation: 'stale' }).length, 1);
    assert.equal(filterTasks(tasks, { q: 'summary 17', category: '', difficulty: '', validation: '' }).length, 1);
  });
  it('lists every task with its validation status', () => {
    const t = text(render(<TasksView tasks={tasks} />));
    assert.match(t, /18 of 18 tasks shown/);
    assert.match(t, /Stale \(task changed\)/);
  });
});

describe('status badge', () => {
  it('uses the documented run state names', () => {
    assert.match(render(<StatusBadge status="awaiting_human" />), /Awaiting human action/);
    assert.match(render(<StatusBadge status="invalidated" />), /Invalidated/);
  });
});

describe('literature evidence', () => {
  const reg = JSON.parse(
    JSON.stringify({
      checkedOn: '2026-11-09',
      themes: { acceptance: 'V-B PR acceptance', productivity: 'V-E Productivity' },
      sources: [
        {
          id: 's1',
          title: 'Paper One',
          authors: ['Ada Lovelace'],
          year: 2026,
          venue: 'MSR',
          url: 'https://example.org/1',
          role: 'r',
          verified: [],
          cautions: ['Quote v1.'],
        },
      ],
      items: [
        {
          id: 'E1',
          theme: 'acceptance',
          source: 's1',
          subject: 'Codex',
          metric: 'Merge rate',
          value: 65.3,
          unit: '%',
          n: 2686,
          conditions: 'pop',
        },
        {
          id: 'E2',
          theme: 'productivity',
          source: 's1',
          subject: 'Copilot',
          metric: 'Pattern',
          value: null,
          unit: 'qualitative',
          conditions: 'tiers',
        },
      ],
      features: {
        checkedOn: '2026-11-09',
        autonomyScale: { L1: 'Suggestion' },
        assistants: ASSISTANT_IDS.map((id) => ({
          id,
          name: id,
          vendor: 'v',
          interactionModes: ['m'],
          autonomy: ['L3'],
          context: 'c',
          tooling: 't',
          execution: 'e',
          deployment: 'd',
          prOutput: 'p',
          sources: ['https://example.org'],
        })),
      },
    }),
  );
  it('labels figures as published secondary data and links each to its source', () => {
    const t = text(render(<EvidenceView reg={reg} />));
    assert.match(t, /not results measured on this platform/);
    assert.match(t, /65\.3% n = 2,686/);
    assert.match(t, /qualitative/);
    assert.match(t, /Lovelace 2026/);
    assert.match(t, /Quote v1\./);
  });
  it('filters by section and text', () => {
    assert.equal(filterEvidence(reg.items, 'acceptance', '').length, 1);
    assert.equal(filterEvidence(reg.items, '', 'copilot').length, 1);
    assert.equal(formatEvidenceValue(reg.items[0]), '65.3%');
  });
});

describe('SWE-bench Verified benchmark', () => {
  const swe = {
    id: 'django__django-16661',
    title: 'django/django #16661',
    category: 'swebench_verified',
    difficulty: 'medium',
    kind: 'swebench',
    version: 'verified',
    testVersion: 'SWE-bench_Verified',
    taskHash: 'h',
    promptHash: 'p',
    testHash: 't',
    starterHash: 's',
    validationStatus: 'dataset_missing',
    validatedAt: null,
    expectedAcceptanceTotal: null,
    prompt: 'Issue text not available yet.',
    metadata: {
      summary: 'Real GitHub issue',
      difficultyRationale: 'Resolved by 57% of submissions.',
      requiredBehavior: [],
      acceptanceCriteria: [],
      acceptanceTests: [],
      scope: { allowed_paths: [], protected_paths: [] },
      timeLimitMinutes: 30,
      starterFiles: [],
      benchmark: 'swebench_verified',
      swebench: {
        dataset: 'princeton-nlp/SWE-bench_Verified',
        repo: 'django/django',
        base_commit: null,
        tier: 'medium',
        leaderboard_share: 0.5738,
        leaderboard_solved_by: 70,
        dataset_difficulty: null,
        fail_to_pass_count: 2,
        pass_to_pass_count: 40,
        has_dataset: false,
      },
    },
  } as unknown as Task;
  const custom = {
    ...swe,
    id: 'BF-01',
    title: 'Fix',
    category: 'bug_fixing',
    kind: 'standard',
    validationStatus: 'validated',
    metadata: { ...swe.metadata, benchmark: 'custom', swebench: null },
  } as unknown as Task;

  it('labels and filters tasks by benchmark', () => {
    assert.equal(taskBenchmark(swe), 'swebench_verified');
    assert.equal(taskBenchmark({ kind: 'standard', metadata: {} }), 'custom');
    assert.equal(categoryLabel('swebench_verified'), 'SWE-bench Verified');
    const f = { q: '', category: '', difficulty: '', validation: '' };
    assert.equal(filterTasks([swe, custom], { ...f, benchmark: 'swebench_verified' }).length, 1);
    assert.equal(filterTasks([swe, custom], { ...f, benchmark: 'custom' })[0].id, 'BF-01');
    assert.equal(filterTasks([swe, custom], f).length, 2);
  });

  it('shows both benchmarks with counts and tells the user how to download the dataset', () => {
    const t = text(render(<TasksView tasks={[swe, custom]} />));
    assert.match(t, /Custom suite 1/);
    assert.match(t, /SWE-bench Verified 1/);
    assert.match(t, /1 SWE-bench tasks are waiting for their issue text/);
    assert.match(t, /pilot\.py select --ids-from/);
    assert.match(t, /Dataset not downloaded/);
    assert.match(t, /django\/django/);
  });

  it('explains SWE-bench scoring on the task page', () => {
    const t = text(render(<SwebenchTaskDetail t={swe} />));
    assert.match(t, /FAIL_TO_PASS \( 2 tests|FAIL_TO_PASS \(2 tests/);
    assert.match(t, /resolved only if all of them pass/);
    assert.match(t, /57\.4% of submissions resolved it|57% of submissions resolved it/);
  });

  it('benchmark switch marks the active option', () => {
    const html = render(<BenchmarkSwitch value="swebench_verified" onChange={() => {}} counts={{ custom: 18, swebench_verified: 12 }} />);
    assert.match(html, /aria-checked="true"[^>]*>SWE-bench Verified/);
    assert.match(text(html), /Custom suite 18/);
  });
});
