// Fallback production build without Vite: bundles with esbuild and compiles Tailwind CSS through
// the tailwindcss compile() API. `npm run build` (Vite) is the standard path; this script exists
// for environments where only esbuild and tailwindcss are installable, and it is what the
// project's own end-to-end smoke test uses in CI-like sandboxes.
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const require = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.join(root, 'dist');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, 'assets'), { recursive: true });

await esbuild.build({
  entryPoints: [path.join(root, 'src', 'main.tsx')],
  bundle: true,
  format: 'esm',
  minify: true,
  sourcemap: true,
  jsx: 'automatic',
  target: 'es2022',
  loader: { '.css': 'empty' },
  define: { 'process.env.NODE_ENV': '"production"' },
  outfile: path.join(out, 'assets', 'app.js'),
  logLevel: 'warning',
});

const twDir = path.dirname(require.resolve('tailwindcss/package.json'));
const { compile } = await import(path.join(twDir, 'dist', 'lib.mjs'));
const css = fs.readFileSync(path.join(root, 'src', 'styles.css'), 'utf8');
const compiler = await compile(css, {
  base: root,
  loadStylesheet: async (id, base) => {
    const file = id === 'tailwindcss' ? path.join(twDir, 'index.css') : path.resolve(base, id);
    return { path: file, base: path.dirname(file), content: fs.readFileSync(file, 'utf8') };
  },
});
const candidates = new Set();
const walk = (dir) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.(tsx?|html)$/.test(e.name)) for (const m of fs.readFileSync(p, 'utf8').matchAll(/[^\s"'`{}<>=;]+/g)) candidates.add(m[0]);
  }
};
walk(path.join(root, 'src'));
candidates.add('');
fs.writeFileSync(path.join(out, 'assets', 'app.css'), compiler.build([...candidates]));

const html = fs
  .readFileSync(path.join(root, 'index.html'), 'utf8')
  .replace('<script type="module" src="/src/main.tsx"></script>', '<script type="module" src="/assets/app.js"></script>')
  .replace('</head>', '    <link rel="stylesheet" href="/assets/app.css" />\n  </head>');
fs.writeFileSync(path.join(out, 'index.html'), html);
console.log(`built ${path.relative(process.cwd(), out)} (${candidates.size} class candidates scanned)`);
