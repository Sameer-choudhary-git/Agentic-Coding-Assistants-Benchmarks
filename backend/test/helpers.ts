import fs from 'node:fs';
import type { AddressInfo } from 'node:net';
import os from 'node:os';
import path from 'node:path';
import type { Server } from 'node:http';
import { createApp } from '../src/app.ts';
import { type Config, loadConfig, REPO_ROOT } from '../src/config.ts';
import { Database } from '../src/db/database.ts';
import { silentLogger } from '../src/logger.ts';
import { createServices, type Services } from '../src/services/container.ts';

export const PYTHON = process.env.ACB_TEST_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');

export interface TestEnv {
  dir: string;
  cfg: Config;
  services: Services;
  server: Server;
  base: string;
  close(): Promise<void>;
}

export function tempDir(prefix = 'acb-test-'): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export function testConfig(dir: string, overrides: Record<string, string> = {}): Config {
  return loadConfig({
    ACB_DB_PATH: path.join(dir, 'db', 'acb.sqlite'),
    ACB_ARTIFACT_ROOT: path.join(dir, 'artifacts'),
    ACB_WORKSPACE_ROOT: path.join(dir, 'workspaces'),
    ACB_PYTHON: PYTHON,
    ACB_EVAL_MODE: 'local',
    ACB_OPERATOR: 'tester',
    ACB_MACHINE_ID: 'test-machine',
    ACB_ENABLE_AUTOMATION: '0',
    ...overrides,
  });
}

export async function startEnv(overrides: Record<string, string> = {}, dir = tempDir(), sync = true): Promise<TestEnv> {
  const cfg = testConfig(dir, overrides);
  const services = createServices(cfg, silentLogger, new Database(cfg.ACB_DB_PATH));
  services.runs.recoverInterrupted();
  if (sync) await services.tasks.sync();
  await services.assistants.detectAll();
  const app = createApp(services);
  const server = await new Promise<Server>((resolve) => {
    const s = app.listen(0, '127.0.0.1', () => resolve(s));
  });
  const { port } = server.address() as AddressInfo;
  return {
    dir,
    cfg,
    services,
    server,
    base: `http://127.0.0.1:${port}/api/v1`,
    async close() {
      await services.runs.idle();
      await new Promise((r) => server.close(r));
      services.db.close();
    },
  };
}

export async function api<T = any>(
  env: TestEnv,
  method: string,
  url: string,
  body?: unknown,
): Promise<{ status: number; body: T; text: string; headers: Headers }> {
  const res = await fetch(env.base + url, {
    method,
    headers: body === undefined ? {} : { 'content-type': 'application/json' },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
  });
  const text = await res.text();
  let parsed: unknown = text;
  try {
    parsed = JSON.parse(text);
  } catch {
    /* not JSON */
  }
  return { status: res.status, body: parsed as T, text, headers: res.headers };
}

export function taskDir(taskId: string): string {
  for (const cat of fs.readdirSync(path.join(REPO_ROOT, 'benchmark_tasks'))) {
    const catDir = path.join(REPO_ROOT, 'benchmark_tasks', cat);
    if (!fs.statSync(catDir).isDirectory()) continue;
    for (const d of fs.readdirSync(catDir)) {
      if (d.startsWith(`${taskId}_`)) return path.join(catDir, d);
    }
  }
  throw new Error(`task ${taskId} not found`);
}

/** Copy a task's reference solution over a workspace (used to simulate a correct submission). */
export function applyReference(taskId: string, workspace: string): void {
  const ref = path.join(taskDir(taskId), 'reference');
  fs.cpSync(ref, workspace, { recursive: true });
}

export function referenceFiles(taskId: string): { path: string; content: string }[] {
  const ref = path.join(taskDir(taskId), 'reference');
  const out: { path: string; content: string }[] = [];
  const walk = (d: string) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) walk(p);
      else out.push({ path: path.relative(ref, p).split(path.sep).join('/'), content: fs.readFileSync(p, 'utf8') });
    }
  };
  walk(ref);
  return out;
}
