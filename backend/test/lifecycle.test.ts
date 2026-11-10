import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { describe, it } from 'node:test';
import { api, PYTHON, referenceFiles, startEnv, taskDir, tempDir } from './helpers.ts';

async function oneRunExperiment(env: Awaited<ReturnType<typeof startEnv>>, taskId = 'BF-01', assistant = 'claude_code') {
  const exp = await api(env, 'POST', '/experiments', { name: 'One', taskIds: [taskId], assistantIds: [assistant], attempts: 1 });
  assert.equal(exp.status, 201, exp.text);
  await api(env, 'POST', `/experiments/${exp.body.experiment.id}/start`);
  const runs = (await api(env, 'GET', `/runs?experimentId=${exp.body.experiment.id}`)).body.runs;
  return { experimentId: exp.body.experiment.id as string, runId: runs[0].id as string };
}

describe('persistence and recovery', () => {
  it('keeps experiments, runs and results across a restart and recovers interrupted evaluations', async () => {
    const dir = tempDir();
    const first = await startEnv({}, dir);
    const { experimentId, runId } = await oneRunExperiment(first);
    await api(first, 'POST', `/runs/${runId}/prepare`);
    await api(first, 'POST', `/runs/${runId}/start`);
    await api(first, 'POST', `/runs/${runId}/submit`, { submissionType: 'files', files: referenceFiles('BF-01') });
    await first.services.runs.idle();
    const before = (await api(first, 'GET', `/results/summary?experimentId=${experimentId}`)).body;
    assert.equal(before.overall.successes, 1);
    // Simulate a crash during a later evaluation: a run stuck in 'evaluating' with a running evaluation.
    const second = await oneRunExperiment(first, 'BF-02');
    await api(first, 'POST', `/runs/${second.runId}/prepare`);
    await api(first, 'POST', `/runs/${second.runId}/start`);
    await api(first, 'POST', `/runs/${second.runId}/submit`, { submissionType: 'workspace', autoEvaluate: false });
    const evaluation = first.services.repos.evaluations.create(second.runId, 'local');
    first.services.repos.runs.update(second.runId, { status: 'evaluating', latestEvaluationId: evaluation.id });
    await first.close();

    const restarted = await startEnv({}, dir, false);
    const after = (await api(restarted, 'GET', `/results/summary?experimentId=${experimentId}`)).body;
    assert.deepEqual(after.overall, before.overall);
    const run = (await api(restarted, 'GET', `/runs/${runId}`)).body;
    assert.equal(run.run.status, 'completed');
    assert.equal(run.run.success, true);
    const recovered = (await api(restarted, 'GET', `/runs/${second.runId}`)).body;
    assert.equal(recovered.run.status, 'submitted');
    assert.equal(recovered.evaluations[0].status, 'error');
    assert.equal(recovered.evaluations[0].errorClass, 'interrupted');
    assert.ok(recovered.events.some((e: { type: string }) => e.type === 'evaluation_interrupted'));
    const again = await api(restarted, 'POST', `/runs/${second.runId}/evaluate`);
    assert.equal(again.status, 202);
    await restarted.services.runs.idle();
    assert.equal((await api(restarted, 'GET', `/runs/${second.runId}`)).body.run.status, 'completed');
    await restarted.close();
  });
});

describe('evaluator failure handling', () => {
  it('classifies an unavailable evaluator as an operational failure that can be re-evaluated', async () => {
    const dir = tempDir();
    const env = await startEnv({}, dir);
    const { runId } = await oneRunExperiment(env);
    await api(env, 'POST', `/runs/${runId}/prepare`);
    await api(env, 'POST', `/runs/${runId}/start`);
    await env.close();

    const broken = await startEnv({ ACB_PYTHON: 'definitely-not-python-xyz' }, dir, false);
    await api(broken, 'POST', `/runs/${runId}/submit`, { submissionType: 'workspace' });
    await broken.services.runs.idle();
    const failed = (await api(broken, 'GET', `/runs/${runId}`)).body.run;
    assert.equal(failed.status, 'failed');
    assert.equal(failed.failureClass, 'evaluator_error');
    assert.equal(failed.success, null);
    const summary = (await api(broken, 'GET', '/results/summary')).body;
    assert.equal(summary.overall.completed, 0, 'operational failures never count as functional results');
    assert.equal(summary.overall.operationalFailures, 1);
    await broken.close();

    const fixed = await startEnv({ ACB_PYTHON: PYTHON }, dir, false);
    const r = await api(fixed, 'POST', `/runs/${runId}/evaluate`);
    assert.equal(r.status, 202);
    await fixed.services.runs.idle();
    const run = (await api(fixed, 'GET', `/runs/${runId}`)).body;
    assert.equal(run.run.status, 'completed');
    assert.equal(run.evaluations.length, 2, 'both evaluations are kept');
    await fixed.close();
  });

  it('applies the time limit: over-time runs count as functional failures', async () => {
    const env = await startEnv();
    const { runId } = await oneRunExperiment(env);
    await api(env, 'POST', `/runs/${runId}/prepare`);
    await api(env, 'POST', `/runs/${runId}/start`);
    const run = env.services.repos.runs.get(runId)!;
    env.services.repos.runs.update(runId, {
      startedAt: new Date(Date.parse(run.startedAt!) - (run.timeLimitSeconds + 5) * 1000).toISOString(),
    });
    await api(env, 'POST', `/runs/${runId}/submit`, { submissionType: 'files', files: referenceFiles('BF-01') });
    await env.services.runs.idle();
    const detail = (await api(env, 'GET', `/runs/${runId}`)).body;
    assert.equal(detail.run.timedOut, true);
    assert.equal(detail.latestEvaluation.success, true, 'the evaluator verdict is preserved');
    assert.equal(detail.run.success, false);
    assert.equal(detail.run.failureClass, 'timeout');
    assert.equal(detail.run.outcome, 'time_limit_exceeded');
    await env.close();
  });

  it('refuses to prepare a run whose frozen task version changed', async () => {
    const env = await startEnv();
    const { runId } = await oneRunExperiment(env);
    env.services.repos.runs.update(runId, {});
    env.services.db.run('UPDATE runs SET task_hash = ? WHERE id = ?', 'f'.repeat(64), runId);
    const r = await api(env, 'POST', `/runs/${runId}/prepare`);
    assert.equal(r.status, 409);
    await env.close();
  });
});

describe('assistant adapters', () => {
  it('reports capability honestly when no CLI is configured', async () => {
    const env = await startEnv({}, tempDir());
    const list = (await api(env, 'GET', '/assistants')).body.assistants as { id: string; capabilityStatus: string }[];
    assert.deepEqual(
      list.map((a) => a.id),
      ['copilot', 'cursor', 'claude_code', 'codex'],
    );
    for (const a of list)
      assert.ok(['requires_manual_execution', 'not_configured'].includes(a.capabilityStatus), `${a.id}: ${a.capabilityStatus}`);
    const { runId } = await oneRunExperiment(env);
    await api(env, 'POST', `/runs/${runId}/prepare`);
    const r = await api(env, 'POST', `/runs/${runId}/automate`);
    assert.equal(r.status, 409);
    const upd = await api(env, 'PATCH', '/assistants/codex', { version: 'codex-cli 0.50.0', model: 'gpt-5-codex' });
    assert.equal(upd.body.assistant.operatorReportedVersion, 'codex-cli 0.50.0');
    await env.close();
  });

  it('runs a configured headless CLI through the common adapter interface', async () => {
    const dir = tempDir();
    const fake = path.join(dir, 'fake-agent.mjs');
    // A stand-in "assistant" used only for testing the adapter plumbing: it copies the task's
    // reference solution into the workspace. It is never used for research results.
    fs.writeFileSync(
      fake,
      `import fs from 'node:fs';\nif (process.argv[2] === '--version') { console.log('fake-agent 0.0.1'); process.exit(0); }\n` +
        `const prompt = fs.readFileSync(process.argv[2], 'utf8');\nif (!prompt.includes('Fix pagination')) process.exit(3);\n` +
        `fs.cpSync(process.env.FAKE_REFERENCE_DIR, process.cwd(), { recursive: true });\nconsole.log('done');\n`,
    );
    process.env.FAKE_REFERENCE_DIR = path.join(taskDir('BF-01'), 'reference');
    process.env.ACB_CLAUDE_CODE_CMD = JSON.stringify([process.execPath, fake, '{prompt_file}']);
    process.env.ANTHROPIC_API_KEY = 'test-placeholder';
    try {
      const env = await startEnv({ ACB_ENABLE_AUTOMATION: '1' }, dir);
      try {
        const claude = (await api(env, 'GET', '/assistants')).body.assistants.find((a: { id: string }) => a.id === 'claude_code');
        assert.equal(claude.capabilityStatus, 'supported', claude.capabilityDetail);
        assert.equal(claude.detectedVersion, 'fake-agent 0.0.1');
        const exp = await api(env, 'POST', '/experiments', {
          name: 'Auto',
          taskIds: ['BF-01'],
          assistantIds: ['claude_code'],
          attempts: 1,
          executionMode: 'automated',
        });
        await api(env, 'POST', `/experiments/${exp.body.experiment.id}/start`);
        const runId = (await api(env, 'GET', `/runs?experimentId=${exp.body.experiment.id}`)).body.runs[0].id;
        await api(env, 'POST', `/runs/${runId}/prepare`);
        const r = await api(env, 'POST', `/runs/${runId}/automate`);
        assert.equal(r.status, 202, r.text);
        await env.services.runs.idle();
        const detail = (await api(env, 'GET', `/runs/${runId}`)).body;
        assert.equal(detail.run.executionMode, 'automated');
        assert.equal(detail.run.status, 'completed');
        assert.equal(detail.run.success, true);
        assert.equal(detail.run.assistantVersionSource, 'detected');
        assert.ok(detail.artifacts.some((a: { kind: string }) => a.kind === 'adapter_output'));
        assert.ok(detail.events.some((e: { type: string }) => e.type === 'adapter_finished'));
      } finally {
        await env.close();
      }
    } finally {
      delete process.env.ACB_CLAUDE_CODE_CMD;
      delete process.env.ANTHROPIC_API_KEY;
      delete process.env.FAKE_REFERENCE_DIR;
    }
  });
});

describe('team data exchange', () => {
  it('imports a bundle idempotently and refuses tampered bundles', async () => {
    const source = await startEnv();
    const { experimentId, runId } = await oneRunExperiment(source);
    await api(source, 'POST', `/runs/${runId}/prepare`);
    await api(source, 'POST', `/runs/${runId}/start`);
    await api(source, 'POST', `/runs/${runId}/submit`, { submissionType: 'files', files: referenceFiles('BF-01') });
    await source.services.runs.idle();
    const bundle = (await api(source, 'GET', `/results/export?format=bundle&experimentId=${experimentId}`)).body;
    await source.close();

    const target = await startEnv();
    const first = await api(target, 'POST', '/results/import', bundle);
    assert.equal(first.status, 200, first.text);
    assert.equal(first.body.inserted.experiments, 1);
    assert.equal(first.body.inserted.runs, 1);
    assert.equal(first.body.inserted.evaluations, 1);
    assert.equal(first.body.conflicts.length, 0);
    const second = await api(target, 'POST', '/results/import', bundle);
    assert.equal(second.body.inserted.runs, undefined);
    assert.equal(second.body.skippedIdentical.runs, 1);
    const summary = (await api(target, 'GET', `/results/summary?experimentId=${experimentId}`)).body;
    assert.equal(summary.overall.successes, 1);
    const tampered = structuredClone(bundle);
    tampered.data.runs[0].success = 0;
    const bad = await api(target, 'POST', '/results/import', tampered);
    assert.equal(bad.status, 400);
    assert.match(bad.body.error.message, /checksum/);
    await target.close();
  });
});
