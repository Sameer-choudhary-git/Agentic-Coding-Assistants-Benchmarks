// End-to-end smoke test of the core workflow through the real UI:
//   empty dashboard -> create 144-attempt experiment -> start -> human-operated run ->
//   submit -> evaluation -> dashboard/results show stored data -> CSV export.
// Requires: built frontend (frontend/dist), Python evaluator environment, and Playwright with a
// Chromium browser (`npx playwright install chromium`). Uses temporary directories and the local
// evaluation mode; nothing is written to the project's database.
//
// The "assistant" in this test is the test itself copying the task's reference solution into the
// workspace. It exercises the plumbing only and is never a research result.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? 'playwright');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'acb-e2e-'));
const port = 4100 + Math.floor(Math.random() * 500);
const base = `http://127.0.0.1:${port}`;

const server = spawn(process.execPath, ['--disable-warning=ExperimentalWarning', '--import', 'tsx', 'src/index.ts'], {
  cwd: path.join(root, 'backend'),
  env: {
    ...process.env,
    PORT: String(port),
    ACB_DB_PATH: path.join(tmp, 'acb.sqlite'),
    ACB_ARTIFACT_ROOT: path.join(tmp, 'artifacts'),
    ACB_WORKSPACE_ROOT: path.join(tmp, 'workspaces'),
    ACB_EVAL_MODE: 'local',
    ACB_OPERATOR: 'e2e',
    LOG_LEVEL: 'warn',
  },
  stdio: ['ignore', 'inherit', 'inherit'],
});

const step = (msg) => console.log(`  ✓ ${msg}`);
let failed = false;
let browser;
try {
  for (let i = 0; i < 60; i += 1) {
    try {
      const r = await fetch(`${base}/api/v1/health`);
      if (r.ok && (await r.json()).benchmarks?.custom === 18) break;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  step('backend started with 18 custom tasks (plus SWE-bench Verified tasks)');

  browser = await chromium.launch();
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  await page.goto(base);
  await page.getByText('No experimental data yet').first().waitFor();
  step('empty dashboard shows "No experimental data yet"');

  await page.goto(`${base}/experiments/new`);
  await page.getByText('18 tasks × 4 assistants × 2 attempts').waitFor();
  const count = await page.locator('p.text-5xl').innerText();
  if (count.trim() !== '144') throw new Error(`planned count shows ${count}`);
  step('new experiment form shows 144 planned attempts');

  await page.getByLabel('Name').fill('E2E smoke');
  await page.getByRole('button', { name: 'Review and create' }).click();
  await page.getByRole('button', { name: 'Create experiment' }).click();
  await page.getByRole('heading', { name: 'E2E smoke' }).waitFor();
  await page.getByRole('button', { name: 'Start experiment' }).click();
  await page.locator('dialog').getByRole('button', { name: 'Start experiment' }).click();
  await page.getByRole('link', { name: 'Open next run in order' }).waitFor();
  step('experiment created and started');

  await page.getByRole('link', { name: 'Open next run in order' }).click();
  const title = await page.locator('h1').innerText();
  const taskId = title.split(' ')[0];
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await page.getByRole('button', { name: 'Start session timer' }).click();
  await page.getByRole('button', { name: 'Log follow-up prompt' }).waitFor();
  step(`run for ${taskId} prepared and started`);

  // Operator applies the "assistant's" changes in the workspace folder.
  const runId = page.url().split('/').pop();
  const detail = await (await fetch(`${base}/api/v1/runs/${runId}`)).json();
  const tasksRoot = path.join(root, 'benchmark_tasks');
  const taskDir = fs.readdirSync(tasksRoot).flatMap((c) => {
    const d = path.join(tasksRoot, c);
    return fs.statSync(d).isDirectory()
      ? fs
          .readdirSync(d)
          .filter((x) => x.startsWith(`${taskId}_`))
          .map((x) => path.join(d, x))
      : [];
  })[0];
  fs.cpSync(path.join(taskDir, 'reference'), detail.run.workspacePath, { recursive: true });

  await page.getByRole('button', { name: 'Log intervention' }).click();
  await page.getByRole('button', { name: 'Stop timer' }).click();
  await page.getByRole('button', { name: 'Submit and evaluate' }).click();
  await page.getByText('Passed', { exact: true }).first().waitFor({ timeout: 120_000 });
  step('submission evaluated: Passed');

  await page.goto(base);
  await page.getByText('Overall measured success').waitFor();
  const success = await page.getByText('1 of 1 completed runs').count();
  if (!success) throw new Error('dashboard does not show the stored result');
  step('dashboard reads the stored result');

  const csv = await (await fetch(`${base}/api/v1/results/export?format=csv`)).text();
  const [header, ...rows] = csv.trim().split('\n');
  if (!header.includes('run_id') || !header.includes('success') || rows.length !== 144) throw new Error('unexpected CSV export');
  step('CSV export contains 144 run rows with expected columns');
  if (pageErrors.length) throw new Error(`page errors: ${pageErrors.join('; ')}`);
  console.log('E2E smoke test passed');
} catch (err) {
  failed = true;
  console.error('E2E smoke test FAILED:', err);
} finally {
  await browser?.close();
  server.kill();
  fs.rmSync(tmp, { recursive: true, force: true });
  process.exitCode = failed ? 1 : 0;
}
