import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { z } from 'zod';

const here = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(here, '..', '..');
export const PLATFORM_VERSION = '1.0.0';

/** Minimal .env loader (KEY=VALUE lines). Values already present in the environment win. */
export function loadDotEnv(file = path.join(REPO_ROOT, '.env')): void {
  if (!fs.existsSync(file)) return;
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

/** True when running inside WSL on a Windows drive (e.g. /mnt/d/...). */
export function onWslWindowsDrive(root = REPO_ROOT): boolean {
  if (process.platform !== 'linux' || !/^\/mnt\/[a-z]\//i.test(root)) return false;
  if (process.env.WSL_DISTRO_NAME) return true;
  try {
    return /microsoft/i.test(fs.readFileSync('/proc/version', 'utf8'));
  } catch {
    return false;
  }
}

/**
 * SQLite's WAL mode needs shared memory, which Windows drives mounted into WSL do not support ("disk I/O
 * error"). Sharing one database file between a Windows and a WSL process is also unsafe. So a WSL run on a
 * Windows drive keeps its own database in the Linux home directory unless ACB_DB_PATH says otherwise.
 */
function defaultDbPath(): string {
  return onWslWindowsDrive() ? path.join(os.homedir(), '.acb', 'acb.sqlite') : path.join(REPO_ROOT, 'data', 'acb.sqlite');
}

function defaultPython(): string {
  if (process.env.VIRTUAL_ENV) {
    const active = path.join(process.env.VIRTUAL_ENV, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    if (fs.existsSync(active)) return active;
  }
  const candidates =
    process.platform === 'win32'
      ? [path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe')]
      : [path.join(REPO_ROOT, '.venv-wsl', 'bin', 'python'), path.join(REPO_ROOT, '.venv', 'bin', 'python')];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  return process.platform === 'win32' ? 'python' : 'python3';
}

const schema = z.object({
  PORT: z.coerce.number().int().min(0).max(65535).default(4000),
  HOST: z.string().default('127.0.0.1'),
  ACB_DB_PATH: z.string().default(defaultDbPath()),
  ACB_ARTIFACT_ROOT: z.string().default(path.join(REPO_ROOT, 'artifacts')),
  ACB_WORKSPACE_ROOT: z.string().default(path.join(os.homedir(), 'acb-workspaces')),
  ACB_PYTHON: z.string().default(defaultPython()),
  ACB_EVAL_MODE: z.enum(['docker', 'local']).default('docker'),
  ACB_EVAL_CONCURRENCY: z.coerce.number().int().min(1).max(4).default(1),
  ACB_EVALUATOR_TIMEOUT_SECONDS: z.coerce.number().int().min(30).default(1800),
  /** SWE-bench scoring builds Docker images on first use; allow much longer. */
  ACB_SWEBENCH_EVAL_TIMEOUT_SECONDS: z.coerce.number().int().min(60).default(7200),
  ACB_OPERATOR: z.string().default(os.userInfo().username || 'unknown'),
  ACB_MACHINE_ID: z.string().default(os.hostname()),
  ACB_MAX_PATCH_BYTES: z.coerce.number().int().min(1024).default(2_000_000),
  ACB_ENABLE_AUTOMATION: z.enum(['0', '1']).default('0'),
  ACB_ALLOWED_ORIGINS: z.string().default('http://localhost:5173,http://127.0.0.1:5173'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export type Config = z.infer<typeof schema> & { repoRoot: string };

export function loadConfig(overrides: Record<string, string | undefined> = {}): Config {
  const parsed = schema.safeParse({ ...process.env, ...overrides });
  if (!parsed.success) {
    const issues = parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ');
    throw new Error(`Invalid configuration: ${issues}`);
  }
  // Relative paths in .env are relative to the repository root; "~" means the home directory.
  const resolvePath = (p: string) =>
    p === ':memory:' ? p : path.resolve(REPO_ROOT, p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p);
  const cfg = {
    ...parsed.data,
    ACB_DB_PATH: resolvePath(parsed.data.ACB_DB_PATH),
    ACB_ARTIFACT_ROOT: resolvePath(parsed.data.ACB_ARTIFACT_ROOT),
    ACB_WORKSPACE_ROOT: resolvePath(parsed.data.ACB_WORKSPACE_ROOT),
    ACB_PYTHON: /[\\/]/.test(parsed.data.ACB_PYTHON) ? resolvePath(parsed.data.ACB_PYTHON) : parsed.data.ACB_PYTHON,
    repoRoot: REPO_ROOT,
  };
  const repo = path.resolve(REPO_ROOT);
  const ws = path.resolve(cfg.ACB_WORKSPACE_ROOT);
  if (ws === repo || ws.startsWith(repo + path.sep)) {
    throw new Error(
      'ACB_WORKSPACE_ROOT must be outside the repository so that coding assistants working in a workspace ' +
        'cannot browse hidden tests or reference solutions.',
    );
  }
  return cfg;
}
