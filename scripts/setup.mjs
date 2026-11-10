#!/usr/bin/env node
// One-time setup: create .env from .env.example, create the Python virtual environment, install
// Python requirements, and validate all benchmark tasks. Node packages are installed by
// `npm install` before this script runs.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const win = process.platform === 'win32';
const run = (cmd, args) => {
  console.log(`\n> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { cwd: root, stdio: 'inherit' });
  if (r.error || r.status !== 0) {
    console.error(`Command failed: ${cmd} ${args.join(' ')}`);
    process.exit(1);
  }
};
const major = Number(process.versions.node.split('.')[0]);
const minor = Number(process.versions.node.split('.')[1]);
if (major < 22 || (major === 22 && minor < 13)) {
  console.error(`Node ${process.versions.node} is too old: Node 22.13 or newer is required (built-in SQLite).`);
  process.exit(1);
}
if (!fs.existsSync(path.join(root, '.env'))) {
  fs.copyFileSync(path.join(root, '.env.example'), path.join(root, '.env'));
  console.log('Created .env from .env.example. Review ACB_EVAL_MODE and ACB_OPERATOR.');
}
const venvPython = win ? path.join(root, '.venv', 'Scripts', 'python.exe') : path.join(root, '.venv', 'bin', 'python');
if (!fs.existsSync(venvPython)) {
  const base = process.env.ACB_BASE_PYTHON || (win ? 'py' : 'python3');
  run(base, win && base === 'py' ? ['-3', '-m', 'venv', '.venv'] : ['-m', 'venv', '.venv']);
}
run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);
run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt']);
run(venvPython, ['-m', 'evaluator.cli', 'env', '--mode', 'local']);
console.log('\nValidating all 18 tasks (local mode, about one minute)...');
run(venvPython, ['-m', 'evaluator.cli', 'validate', '--mode', 'local', '--dry-run']);
console.log('\nSetup complete. Start the app with: npm run dev');
