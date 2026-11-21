import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';
import { REPO_ROOT } from '../src/config.ts';
import { api, referenceFiles, startEnv, type TestEnv } from './helpers.ts';

const ALL_ASSISTANTS = ['copilot', 'cursor', 'claude_code', 'codex'];

describe('API integration', () => {
  let env: TestEnv;
  let allTaskIds: string[];

  before(async () => {
    env = await startEnv();
  });
  after(async () => {
    await env.close();
  });

  it('reports health', async () => {
    const r = await api(env, 'GET', '/health');
    assert.equal(r.status, 200);
    assert.equal(r.body.status, 'ok');
    assert.equal(r.body.benchmarks.custom, 18);
    assert.equal(r.body.benchmarks.swebench_verified, 12);
    assert.equal(r.body.benchmarks.golden_verified, 67);
    assert.equal(r.body.tasks, 97);
    assert.equal(r.body.database.schemaVersion, 1);
  });

  it('serves the golden dataset overview and only whitelisted figures', async () => {
    const r = await api(env, 'GET', '/golden');
    assert.equal(r.status, 200);
    assert.equal(r.body.nTasks, 350);
    assert.equal(Object.values(r.body.summary.by_domain as Record<string, number>).reduce((a, b) => a + b, 0), 350);
    assert.ok(r.body.results.agents.length > 0);
    assert.ok(r.body.figures.includes('fig1_composition.png'));
    assert.equal((await api(env, 'GET', '/golden/figures/..%2Fresults.json')).status, 404);
  });

  it('discovers all 18 custom tasks with filters', async () => {
    const r = await api(env, 'GET', '/tasks?benchmark=custom');
    assert.equal(r.status, 200);
    allTaskIds = r.body.tasks.map((t: { id: string }) => t.id);
    assert.equal(allTaskIds.length, 18);
    const counts: Record<string, number> = {};
    for (const t of r.body.tasks) counts[t.category] = (counts[t.category] ?? 0) + 1;
    assert.deepEqual(Object.values(counts), [3, 3, 3, 3, 3, 3]);
    assert.ok(r.body.tasks.every((t: { validationStatus: string }) => t.validationStatus === 'validated'));
    const filtered = await api(env, 'GET', '/tasks?category=security_remediation&difficulty=medium');
    assert.deepEqual(
      filtered.body.tasks.map((t: { id: string }) => t.id),
      ['SR-02', 'SR-03'],
    );
  });

  it('lists the 12 SWE-bench Verified tasks separately and keeps them out of experiments until the dataset is downloaded', async () => {
    const r = await api(env, 'GET', '/tasks?benchmark=swebench_verified');
    assert.equal(r.body.tasks.length, 12);
    const t = r.body.tasks[0];
    assert.equal(t.kind, 'swebench');
    assert.equal(t.metadata.benchmark, 'swebench_verified');
    assert.ok(['easy', 'medium', 'hard'].includes(t.difficulty));
    assert.ok(t.metadata.swebench.repo);
    assert.ok(r.body.tasks.every((x: { validationStatus: string }) => x.validationStatus === 'dataset_missing'));
    const sweIds = r.body.tasks.map((x: { id: string }) => x.id);
    const assistantIds = ['copilot', 'cursor', 'claude_code', 'codex'];
    const preview = await api(env, 'POST', '/experiments/preview', { name: 'swe', taskIds: sweIds, assistantIds, attempts: 1 });
    assert.equal(preview.body.plannedAttempts, 48);
    assert.equal(preview.body.benchmark, 'swebench_verified');
    const blocked = await api(env, 'POST', '/experiments', { name: 'swe', taskIds: sweIds, assistantIds, attempts: 1 });
    assert.equal(blocked.status, 422, 'dataset_missing tasks are not validated');
    const mixed = await api(env, 'POST', '/experiments', {
      name: 'mixed',
      taskIds: [sweIds[0], 'BF-01'],
      assistantIds,
      attempts: 1,
      allowUnvalidatedTasks: true,
    });
    assert.equal(mixed.status, 400);
    assert.match(mixed.body.error.message, /one benchmark/);
    const summary = await api(env, 'GET', '/results/summary?benchmark=swebench_verified');
    assert.equal(summary.body.scope.benchmark, 'swebench_verified');
    assert.equal(summary.body.totals.tasks, 12);
  });

  it('serves task detail without hidden tests or reference code', async () => {
    const r = await api(env, 'GET', '/tasks/BF-02');
    assert.equal(r.status, 200);
    assert.match(r.body.task.prompt, /retry-limit/i);
    assert.equal(r.body.task.metadata.acceptanceTests.length, 7);
    const hidden = fs.readFileSync(
      path.join(REPO_ROOT, 'benchmark_tasks/bug_fixing/BF-02_retry_limit_logic/grading/acceptance/test_acceptance.py'),
      'utf8',
    );
    assert.ok(!r.text.includes('def test_delays_are_capped'), 'hidden test code leaked');
    assert.ok(
      !r.text.includes(
        hidden
          .split('\n')
          .find((l) => l.includes('sleeps == [1.0, 3.0'))!
          .trim(),
      ),
    );
    const ref = fs.readFileSync(
      path.join(REPO_ROOT, 'benchmark_tasks/bug_fixing/BF-02_retry_limit_logic/reference/retrykit/retry.py'),
      'utf8',
    );
    assert.ok(!r.text.includes('min(self.base * self.factor ** (retry_number - 1), self.max_delay)') || !ref);
  });

  it('serves starter files but never grading or reference files', async () => {
    const ok = await api(env, 'GET', '/tasks/BF-02/starter?path=retrykit/retry.py');
    assert.equal(ok.status, 200);
    assert.match(ok.body.content, /def retry_call/);
    for (const bad of ['../grading/acceptance/test_acceptance.py', '../reference/retrykit/retry.py', '/etc/passwd', '../../task.json']) {
      const r = await api(env, 'GET', `/tasks/BF-02/starter?path=${encodeURIComponent(bad)}`);
      assert.equal(r.status, 404, bad);
    }
    assert.equal((await api(env, 'GET', '/tasks/NOPE-1')).status, 404);
    assert.equal((await api(env, 'GET', '/tasks/..%2F..')).status, 400);
  });

  it('shows no fabricated results on an empty database', async () => {
    const r = await api(env, 'GET', '/results/summary');
    assert.equal(r.status, 200);
    assert.equal(r.body.hasData, false);
    assert.equal(r.body.overall.successRate, null);
    assert.equal(r.body.overall.completed, 0);
    assert.ok(r.body.byAssistant.every((a: { successRate: null }) => a.successRate === null));
    const csv = await api(env, 'GET', '/results/export?format=csv');
    assert.equal(csv.text.trim().split('\n').length, 1, 'CSV must contain only the header');
    const jsonl = await api(env, 'GET', '/results/export?format=jsonl');
    assert.equal(jsonl.text, '');
  });

  it('previews the full design as 144 planned attempts', async () => {
    const body = { name: 'Full design', taskIds: allTaskIds, assistantIds: ALL_ASSISTANTS, attempts: 2 };
    const r = await api(env, 'POST', '/experiments/preview', body);
    assert.equal(r.status, 200);
    assert.equal(r.body.plannedAttempts, 144);
    assert.equal(r.body.formula, '18 tasks × 4 assistants × 2 attempts');
    assert.ok(r.body.warnings.some((w: string) => /Local evaluation/.test(w)));
  });

  it('validates experiment input', async () => {
    assert.equal((await api(env, 'POST', '/experiments', { name: 'x' })).status, 400);
    assert.equal(
      (await api(env, 'POST', '/experiments', { name: 'bad', taskIds: ['ZZ-9'], assistantIds: ['codex'], attempts: 1 })).status,
      400,
    );
    assert.equal(
      (await api(env, 'POST', '/experiments', { name: 'bad', taskIds: ['BF-01'], assistantIds: ['gpt'], attempts: 1 })).status,
      400,
    );
    assert.equal(
      (await api(env, 'POST', '/experiments', { name: 'bad', taskIds: ['BF-01'], assistantIds: ['codex'], attempts: 0 })).status,
      400,
    );
    assert.equal((await api(env, 'POST', '/experiments', '{"broken json')).status, 400);
  });

  let fullId: string;
  it('creates the 144-attempt experiment matrix with recorded configuration', async () => {
    const r = await api(env, 'POST', '/experiments', {
      name: 'Full design',
      taskIds: allTaskIds,
      assistantIds: ALL_ASSISTANTS,
      attempts: 2,
      seed: 2026,
    });
    assert.equal(r.status, 201);
    assert.equal(r.body.plannedAttempts, 144);
    fullId = r.body.experiment.id;
    const detail = await api(env, 'GET', `/experiments/${fullId}`);
    const planned = detail.body.plannedAttempts as { taskId: string; assistantId: string; attemptNumber: number; sequence: number }[];
    assert.equal(planned.length, 144);
    const keys = new Set(planned.map((p) => `${p.taskId}|${p.assistantId}|${p.attemptNumber}`));
    assert.equal(keys.size, 144);
    assert.deepEqual([...new Set(planned.map((p) => p.sequence))].length, 144);
    const config = detail.body.experiment.config;
    assert.equal(config.tasks.length, 18);
    assert.ok(config.tasks.every((t: { taskHash: string; promptHash: string }) => t.taskHash.length === 64 && t.promptHash.length === 64));
    assert.ok(
      config.assistants.every(
        (a: { versionKnown: boolean; detectedVersion: string | null }) => a.versionKnown === Boolean(a.detectedVersion),
      ),
    );
    assert.equal(detail.body.runs.length, 0);
    assert.equal(detail.body.progress.planned, 144);
  });

  it('starts the experiment, materialising one run per planned attempt', async () => {
    const r = await api(env, 'POST', `/experiments/${fullId}/start`);
    assert.equal(r.status, 200);
    assert.equal(r.body.experiment.status, 'active');
    assert.equal((await api(env, 'POST', `/experiments/${fullId}/start`)).status, 409);
    const runs = await api(env, 'GET', `/runs?experimentId=${fullId}`);
    assert.equal(runs.body.runs.length, 144);
    assert.ok(runs.body.runs.every((x: { status: string }) => x.status === 'planned'));
  });

  let smallId: string;
  const runsByKey: Record<string, string> = {};
  it('creates a small experiment for workflow tests', async () => {
    const r = await api(env, 'POST', '/experiments', {
      name: 'Workflow',
      taskIds: ['BF-01', 'TW-01'],
      assistantIds: ['claude_code', 'codex'],
      attempts: 1,
      randomizeOrder: false,
    });
    assert.equal(r.status, 201);
    smallId = r.body.experiment.id;
    await api(env, 'POST', `/experiments/${smallId}/start`);
    const runs = (await api(env, 'GET', `/runs?experimentId=${smallId}`)).body.runs;
    for (const run of runs) runsByKey[`${run.taskId}|${run.assistantId}`] = run.id;
    assert.equal(runs.length, 4);
  });

  it('rejects invalid lifecycle transitions', async () => {
    const id = runsByKey['BF-01|claude_code'];
    assert.equal((await api(env, 'POST', `/runs/${id}/start`)).status, 409);
    assert.equal((await api(env, 'POST', `/runs/${id}/submit`, {})).status, 409);
    assert.equal((await api(env, 'POST', `/runs/${id}/evaluate`)).status, 409);
    assert.equal((await api(env, 'POST', `/runs/${id}/retry`)).status, 409);
    assert.equal((await api(env, 'GET', '/runs/does-not-exist')).status, 404);
  });

  it('runs the human-operated workflow end to end (correct submission via files)', async () => {
    const id = runsByKey['BF-01|claude_code'];
    const prep = await api(env, 'POST', `/runs/${id}/prepare`);
    assert.equal(prep.status, 200);
    const ws = prep.body.run.workspacePath as string;
    assert.ok(!path.resolve(ws).startsWith(path.resolve(REPO_ROOT)), 'workspace must be outside the repo');
    assert.ok(fs.existsSync(path.join(ws, 'pager', 'paginate.py')));
    assert.ok(!fs.existsSync(path.join(ws, 'grading')) && !fs.existsSync(path.join(ws, 'reference')));
    const start = await api(env, 'POST', `/runs/${id}/start`, { assistantVersion: '2.1.0 (operator)', model: 'test-model' });
    assert.equal(start.body.run.status, 'running');
    assert.equal(start.body.run.iterations, 1);
    await api(env, 'POST', `/runs/${id}/log`, { type: 'iteration', note: 'asked to also run the tests' });
    await api(env, 'POST', `/runs/${id}/log`, { type: 'intervention', note: 'approved a file write' });
    const stop = await api(env, 'POST', `/runs/${id}/stop`);
    assert.equal(stop.body.run.status, 'awaiting_human');
    assert.equal(typeof stop.body.run.wallClockSeconds, 'number');
    const submit = await api(env, 'POST', `/runs/${id}/submit`, {
      submissionType: 'files',
      files: referenceFiles('BF-01'),
      notes: 'files uploaded',
    });
    assert.equal(submit.status, 202);
    assert.equal(submit.body.run.status, 'evaluating');
    await env.services.runs.idle();
    const detail = (await api(env, 'GET', `/runs/${id}`)).body;
    assert.equal(detail.run.status, 'completed');
    assert.equal(detail.run.success, true);
    assert.equal(detail.run.failureClass, null);
    assert.equal(detail.run.iterations, 2);
    assert.equal(detail.run.humanInterventions, 1);
    assert.equal(detail.run.assistantVersion, '2.1.0 (operator)');
    assert.equal(detail.run.assistantVersionSource, 'operator');
    assert.equal(detail.latestEvaluation.status, 'completed');
    assert.equal(detail.latestEvaluation.acceptancePassed, detail.latestEvaluation.acceptanceTotal);
    assert.ok(detail.testOutcomes.some((t: { suite: string }) => t.suite === 'regression'));
    assert.ok(detail.artifacts.some((a: { relativePath: string }) => a.relativePath.endsWith('report.json')));
    assert.ok(detail.events.map((e: { type: string }) => e.type).includes('evaluation_completed'));
    const report = detail.artifacts.find((a: { relativePath: string }) => a.relativePath.endsWith('report.json'));
    const dl = await api(env, 'GET', `/runs/${id}/artifacts/${report.id}`);
    assert.equal(dl.status, 200);
    assert.equal(dl.body.task.id, 'BF-01');
    const other = runsByKey['TW-01|codex'];
    assert.equal((await api(env, 'GET', `/runs/${other}/artifacts/${report.id}`)).status, 404);
  });

  it('records an incorrect submission as a task failure', async () => {
    const id = runsByKey['BF-01|codex'];
    await api(env, 'POST', `/runs/${id}/prepare`);
    await api(env, 'POST', `/runs/${id}/start`);
    const r = await api(env, 'POST', `/runs/${id}/submit`, { submissionType: 'workspace', iterations: 3, humanInterventions: 0 });
    assert.equal(r.status, 202);
    await env.services.runs.idle();
    const run = (await api(env, 'GET', `/runs/${id}`)).body.run;
    assert.equal(run.status, 'completed');
    assert.equal(run.success, false);
    assert.equal(run.failureClass, 'task_failure');
    assert.equal(run.outcome, 'acceptance_failed');
    assert.equal(run.iterations, 3);
  });

  it('applies unified-diff patch submissions and rejects unsafe patches', async () => {
    const id = runsByKey['TW-01|claude_code'];
    const prep = await api(env, 'POST', `/runs/${id}/prepare`);
    await api(env, 'POST', `/runs/${id}/start`);
    const ws = prep.body.run.workspacePath as string;
    const evil = '--- a/../outside.py\n+++ b/../outside.py\n@@ -0,0 +1 @@\n+x = 1\n';
    const bad = await api(env, 'POST', `/runs/${id}/submit`, { submissionType: 'patch', patch: evil });
    assert.equal(bad.status, 400);
    const garbage = await api(env, 'POST', `/runs/${id}/submit`, {
      submissionType: 'patch',
      patch: '--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-nothing\n+else\n',
    });
    assert.equal(garbage.status, 422);
    const tests = referenceFiles('TW-01')[0];
    const lines = tests.content.split('\n');
    if (lines[lines.length - 1] === '') lines.pop();
    const patch = `--- /dev/null\n+++ b/${tests.path}\n@@ -0,0 +1,${lines.length} @@\n${lines.map((l) => `+${l}`).join('\n')}\n`;
    const ok = await api(env, 'POST', `/runs/${id}/submit`, { submissionType: 'patch', patch });
    assert.equal(ok.status, 202, ok.text);
    assert.ok(fs.existsSync(path.join(ws, tests.path)));
    await env.services.runs.idle();
    const detail = (await api(env, 'GET', `/runs/${id}`)).body;
    assert.equal(detail.run.success, true);
    assert.equal(detail.latestEvaluation.mutationScore, 1);
    assert.ok(detail.latestEvaluation.lineCoverage >= 0.9);
    assert.ok(detail.testOutcomes.every((t: { suite: string }) => t.suite !== 'acceptance'));
  });

  it('marks operational failures, preserves them on retry, and supports invalidation and labels', async () => {
    const id = runsByKey['TW-01|codex'];
    await api(env, 'POST', `/runs/${id}/prepare`);
    await api(env, 'POST', `/runs/${id}/start`);
    assert.equal((await api(env, 'POST', `/runs/${id}/fail`, { failureClass: 'task_failure', message: 'nope' })).status, 400);
    const failed = await api(env, 'POST', `/runs/${id}/fail`, {
      failureClass: 'environment_error',
      message: 'laptop rebooted mid-session',
    });
    assert.equal(failed.body.run.status, 'failed');
    const retry = await api(env, 'POST', `/runs/${id}/retry`);
    assert.equal(retry.status, 201);
    assert.equal(retry.body.run.runNumber, 2);
    assert.equal(retry.body.run.retryOfRunId, id);
    assert.equal(retry.body.run.status, 'planned');
    const original = (await api(env, 'GET', `/runs/${id}`)).body;
    assert.equal(original.run.status, 'failed');
    assert.equal(original.run.failureClass, 'environment_error');
    assert.equal(original.siblings.length, 2);
    assert.equal((await api(env, 'POST', `/runs/${id}/retry`)).status, 409, 'only the latest run can be retried');
    const done = runsByKey['BF-01|codex'];
    assert.equal((await api(env, 'POST', `/runs/${done}/retry`)).status, 409, 'completed task failures cannot be retried');
    const labelled = await api(env, 'PATCH', `/runs/${done}/labels`, {
      failureModes: ['incomplete_implementation'],
      notes: 'left boundary bug',
    });
    assert.deepEqual(labelled.body.run.failureModes, ['incomplete_implementation']);
    assert.equal((await api(env, 'PATCH', `/runs/${done}/labels`, { failureModes: ['made_up'] })).status, 400);
    assert.equal((await api(env, 'POST', `/runs/${retry.body.run.id}/invalidate`, { reason: 'x' })).status, 400);
    const inv = await api(env, 'POST', `/runs/${retry.body.run.id}/invalidate`, { reason: 'operator used the wrong prompt' });
    assert.equal(inv.body.run.status, 'invalidated');
  });

  it('summarises stored results with documented denominators', async () => {
    const r = await api(env, 'GET', `/results/summary?experimentId=${smallId}`);
    assert.equal(r.status, 200);
    assert.equal(r.body.hasData, true);
    const o = r.body.overall;
    assert.equal(o.planned, 4);
    assert.equal(o.completed, 3);
    assert.equal(o.successes, 2);
    assert.equal(o.successRate, 2 / 3);
    assert.equal(o.invalidated, 1);
    assert.equal(o.retries, 1);
    const claude = r.body.byAssistant.find((a: { assistantId: string }) => a.assistantId === 'claude_code');
    assert.equal(claude.successes, 2);
    assert.equal(claude.completed, 2);
    const cell = r.body.byAssistantCategory.find(
      (c: { assistantId: string; category: string }) => c.assistantId === 'codex' && c.category === 'bug_fixing',
    );
    assert.equal(cell.exploratory, true);
    assert.equal(cell.successRate, 0);
  });

  it('exports CSV, JSONL, config, summary, dictionary and manifest with expected fields', async () => {
    const csv = await api(env, 'GET', `/results/export?format=csv&experimentId=${smallId}`);
    assert.equal(csv.status, 200);
    assert.match(csv.headers.get('content-disposition') ?? '', /attachment/);
    const [header, ...rows] = csv.text.trim().split('\n');
    for (const col of [
      'run_id',
      'task_id',
      'assistant_id',
      'attempt_number',
      'success',
      'eligible_for_success',
      'wall_clock_seconds',
      'iterations',
      'human_interventions',
      'acceptance_passed',
      'regression_failed',
      'ruff_new',
      'semgrep_status',
      'task_hash',
      'prompt_hash',
      'evaluator_version',
    ]) {
      assert.ok(header.split(',').includes(col), col);
    }
    assert.equal(rows.length, 5, '4 original runs + 1 retry');
    const jsonl = await api(env, 'GET', `/results/export?format=jsonl&experimentId=${smallId}`);
    const records = jsonl.text
      .trim()
      .split('\n')
      .map((l) => JSON.parse(l));
    assert.equal(records.length, 5);
    assert.ok(records.every((r) => 'is_effective_run' in r && Array.isArray(r.evaluations)));
    const config = await api(env, 'GET', `/results/export?format=config&experimentId=${smallId}`);
    assert.equal(config.body.plannedAttempts.length, 4);
    const summary = await api(env, 'GET', `/results/export?format=summary_csv&experimentId=${smallId}`);
    assert.match(summary.text.split('\n')[0], /^group_level,assistant_id,category,planned,completed,successes,success_rate/);
    const dict = await api(env, 'GET', '/results/export?format=dictionary');
    assert.ok(dict.body.length >= 60);
    const manifest = await api(env, 'GET', `/results/export?format=manifest&experimentId=${smallId}`);
    assert.equal(manifest.body.demoDataIncluded, false);
    assert.deepEqual(manifest.body.evaluationModes, ['local']);
    assert.ok(manifest.body.evaluatorVersions.includes('1.0.0'));
    assert.equal(manifest.body.tasks.length, 2);
    assert.equal((await api(env, 'GET', '/results/export?format=pdf')).status, 400);
  });

  it('writes all exports to disk with checksums', async () => {
    const r = await api(env, 'POST', '/results/export-all', { experimentId: smallId });
    assert.equal(r.status, 200);
    assert.ok(fs.existsSync(path.join(r.body.directory, 'CHECKSUMS.json')));
    assert.ok(r.body.files.some((f: { name: string }) => f.name.startsWith('bundle-')));
  });

  it('lists recent activity', async () => {
    const r = await api(env, 'GET', '/events?limit=5');
    assert.equal(r.body.events.length, 5);
  });

  it('rejects oversized request bodies', async () => {
    const big = 'x'.repeat(6 * 1024 * 1024);
    const r = await api(env, 'POST', '/experiments/preview', { name: big });
    assert.equal(r.status, 413);
  });

  it('returns JSON 404 for unknown endpoints', async () => {
    const r = await api(env, 'GET', '/nope');
    assert.equal(r.status, 404);
    assert.equal(r.body.error.code, 'not_found');
  });

  it('serves the literature evidence registry separately from measured results', async () => {
    const r = await api(env, 'GET', '/evidence');
    assert.equal(r.status, 200);
    const ids = new Set(r.body.sources.map((x: { id: string }) => x.id));
    assert.ok(r.body.items.length >= 40);
    assert.ok(r.body.items.every((i: { source: string }) => ids.has(i.source)), 'every figure cites a known source');
    assert.deepEqual(
      r.body.features.assistants.map((a: { id: string }) => a.id),
      ALL_ASSISTANTS,
    );
    const csv = await api(env, 'GET', '/evidence/export?format=csv');
    assert.equal(csv.status, 200);
    assert.match(csv.text.split('\n')[0], /^id,theme,subject,metric,value/);
    const tex = await api(env, 'GET', '/evidence/export?format=latex');
    assert.match(tex.text, /\\begin\{table\*\}/);
    assert.match(tex.text, /\\cite\{pinna2026\}/);
    assert.equal((await api(env, 'GET', '/evidence/export?format=xml')).status, 400);
  });
});
