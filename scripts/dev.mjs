#!/usr/bin/env node
// Start the API (PORT, default 4000) and the Vite dev server (port 5173) together.
// Ctrl+C, or either process exiting, stops BOTH process trees (npm -> sh -> node), so no server is left
// running in the background holding a port.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const isWin = process.platform === 'win32';

// The API port comes from the environment or .env (default 4000); the Vite proxy is pointed at it.
function envPort() {
  if (process.env.PORT) return process.env.PORT;
  try {
    const line = fs
      .readFileSync(path.join(root, '.env'), 'utf8')
      .split(/\r?\n/)
      .find((l) => /^\s*PORT\s*=/.test(l));
    if (line) return line.split('=')[1].trim().replace(/^['"]|['"]$/g, '');
  } catch {
    /* no .env */
  }
  return '4000';
}
const port = envPort();
const env = { ...process.env, PORT: port, ACB_API_URL: process.env.ACB_API_URL ?? `http://127.0.0.1:${port}` };

/** Kill a child and everything it started. */
function killTree(child) {
  if (!child.pid || child.exitCode !== null) return;
  try {
    if (isWin) spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else process.kill(-child.pid, 'SIGTERM'); // negative pid = the whole process group
  } catch {
    /* already gone */
  }
}

// Both servers are started with the same Node that runs this script, never through npm or the
// node_modules/.bin shims. Shims created by `npm install` on Windows start Windows node.exe when run from
// WSL, and a Windows process does not receive the Linux environment (so Vite would ignore ACB_API_URL).
const viteBin = path.join(
  path.dirname(createRequire(path.join(root, 'frontend', 'package.json')).resolve('vite/package.json')),
  'bin',
  'vite.js',
);
const commands = [
  ['backend', path.join(root, 'backend'), ['--disable-warning=ExperimentalWarning', '--watch', '--import', 'tsx', 'src/index.ts']],
  ['frontend', path.join(root, 'frontend'), [viteBin]],
];

let stopping = false;
const children = commands.map(([name, cwd, args]) => {
  // detached on POSIX puts each child in its own process group so killTree reaches grandchildren.
  const child = spawn(process.execPath, args, { cwd, env, stdio: 'inherit', detached: !isWin });
  child.on('exit', (code) => {
    if (!stopping) console.log(`[${name}] exited with code ${code}; stopping the other server too`);
    stop(code ?? 0);
  });
  return child;
});

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const c of children) killTree(c);
  setTimeout(() => process.exit(code), 500);
}
process.on('SIGINT', () => stop(0));
process.on('SIGTERM', () => stop(0));
process.on('SIGHUP', () => stop(0));

console.log(`\n  App:  http://127.0.0.1:5173 (Vite picks the next free port if 5173 is busy)\n  API:  ${env.ACB_API_URL}/api/v1/health\n`);
