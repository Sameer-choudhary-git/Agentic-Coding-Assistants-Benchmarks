#!/usr/bin/env node
// Run the project's Python (the .venv interpreter if it exists) with the given arguments.
// Keeps npm scripts identical on Windows, macOS and Linux.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const venv = process.platform === 'win32' ? path.join(root, '.venv', 'Scripts', 'python.exe') : path.join(root, '.venv', 'bin', 'python');
const python = process.env.ACB_PYTHON || (fs.existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3');
const result = spawnSync(python, process.argv.slice(2), { cwd: root, stdio: 'inherit', env: { ...process.env, PYTHONUTF8: '1' } });
if (result.error) {
  console.error(`Cannot run ${python}: ${result.error.message}. Run "npm run setup" or set ACB_PYTHON.`);
  process.exit(1);
}
process.exit(result.status ?? 1);
