# Test report (delivery, 5 Nov 2026)

Executed in the build environment (Linux, Node 22.23, Python 3.13, Ruff 0.16, no Docker daemon,
no Semgrep, no assistant CLIs). npm/PyPI were blocked there, so Express and type packages were
fetched from their GitHub release tags and the frontend was built with `frontend/scripts/build-offline.mjs`
(esbuild + Tailwind) instead of Vite.

| Suite | Command | Result |
|---|---|---|
| Task validation (18 tasks, local mode) | `python -m evaluator.cli validate --mode local` | 18/18 validated |
| Python: evaluator, tasks, workspace, schemas, analysis | `python -m pytest` | 53 passed |
| Python lint | `ruff check .` | passed |
| Backend type-check | `tsc --noEmit` (backend) | passed |
| Backend: unit, API integration, lifecycle, recovery, adapters, import/export | `npm run test:backend` | 41 passed |
| Frontend type-check | `tsc --noEmit` (frontend) | passed |
| Frontend components and views | `npm run test:frontend` | 12 passed |
| End-to-end UI smoke test (Playwright, Chromium) | `node tests/e2e/smoke.mjs` | passed |

The required checks from the build prompt are covered: app starts (e2e, health), 18 tasks
discoverable, experiment creation, 144-attempt matrix, human-operated submission, evaluator
records results, persistence after restart, dashboard reads stored data, CSV/JSONL fields, empty
database shows no fabricated results.

## Not executed in the build environment

* **Docker evaluation mode** (no Docker daemon): run `npm run docker:evaluator` then
  `python -m evaluator.cli validate --mode docker`.
* **Semgrep** (not installable): rules in `evaluator/config/semgrep/rules.yml` were never run; check with
  `semgrep --validate --config evaluator/config/semgrep/rules.yml`.
* **Vite dev server/build, Windows PowerShell setup**: run `npm install`, `npm run setup`, `npm run dev`.
* **Real assistant CLIs**: none installed; adapters tested only with a stand-in script.
