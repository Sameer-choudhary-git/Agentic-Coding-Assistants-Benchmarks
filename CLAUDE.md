# Project context for Claude Code

This repository is a research platform that compares agentic coding assistants (GitHub Copilot, Cursor,
Claude Code, OpenAI Codex) on real coding tasks. It is for a paper based on "Agentic Coding Assistants: A
Comparative Study of GitHub Copilot, Cursor, Claude Code and Codex". The owner works on it from two laptops.
Code is shared through GitHub; each laptop runs and scores tasks in its own environment.

Read these first:
- `docs/PROJECT_STATUS.md`: what has been built, what is verified, what is left, and known pitfalls
- `docs/EVALUATION_GUIDE.md`: setup, study protocol, scoring, the score table, and all the logic and design decisions
- `golden/reports/RESEARCH_REPORT.md`: the dataset's method write-up for the paper

## Working with the owner
- Keep answers short.
- Do not run full test suites or long jobs unless asked: the owner wants to limit usage. Run only the tests for
  what you changed.
- Commit or push only when asked. The working branch is `feat/golden-dataset`; `main` has only the first commit.
- The golden dataset and the balanced core are the most important part. Do not change
  `golden/configs/core_review.yaml` or the dataset files without saying why.

## Layout
- `golden/`: dataset pipeline (`agentbench/`), dataset (`dataset/`), configs, report, helper `scripts/`
- `evaluator/`: workspace creation, scoring (`swebench.py`), patch quality (`patch_quality.py`), custom suite
- `backend/` (Express + SQLite) and `frontend/` (React + Vite): the app; `npm run dev` starts both
- `benchmark_tasks/`: the 18-task custom suite; `swebench_pilot/`: the 12-task SWE-bench Verified pilot

## Tests (run only what you touched)
- Python: `python -m pytest -q tests/evaluator/<file>.py` and `python -m pytest -q golden/tests`
- Backend: `node --disable-warning=ExperimentalWarning --import tsx --test test/<file>.test.ts` (in `backend/`)
- Frontend: `node --import tsx --test test/components.test.tsx` (in `frontend/`)
- Type-check: `npm run typecheck`
