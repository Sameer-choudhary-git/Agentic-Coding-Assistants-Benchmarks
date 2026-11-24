# Project status and history

Last updated 2026-11-24. This file carries the context of the work done so far, so the project can be continued
from any laptop or in any new Claude Code session. For how-to and logic, see `docs/EVALUATION_GUIDE.md`.

## 1. What exists

| Part | State |
|---|---|
| Golden dataset (`golden/`) | 350 tasks in 8 domains from 8 public sources (SWE-bench Verified, ++, +, Pro, Multimodal, Multilingual, SWE-rebench, NYU CTF), quality gates, rule-based domain classifier, calibrated difficulty, stratified sampling, code quality score for every reference fix |
| Runnable in the app | 249 tasks (247 shown; 2 are already pilot tasks): 6 domains, scored by the official SWE-bench harness or SWE-bench Pro's scripts in Docker |
| Balanced core | 30 tasks, 5 per domain, reviewed by hand (`golden/configs/core_review.yaml`): 20 of 64 automatic labels were wrong and corrected |
| Correctness scoring | Hidden FAIL_TO_PASS + PASS_TO_PASS tests in Docker (`evaluator/swebench.py`) |
| Code quality scoring | Every patch gets a 0–100 QualityScore from the same module that scored the reference fixes (`evaluator/patch_quality.py`) |
| App | Golden benchmark, balanced core pre-selected, domain-balanced success, quality table on Results, quality panel on each run, Golden dataset page, CSV export with quality columns |
| Paper tables | `golden/scripts/score_table.py` (success with CIs, domain-balanced, by domain, quality, pairwise McNemar) |
| CI | GitHub Actions `CI` and `golden-ci` both green on `feat/golden-dataset` |

## 2. What is verified (on laptop 1, 2026-11-24)

- **Scoring smoke test** (`golden/scripts/smoke_harness.py`): the reference fix of one task per source resolved in
  Docker. The tasks were caddy-6115 (Multilingual), NodeBB-97c8569a79 (Pro), react-pdf-1280 (Multimodal) and
  django-16801 (Verified).
  - App quality score = stored reference score (97.0 and 100.0).
  - Negative controls (a patch that changes nothing) on caddy and NodeBB were **not** resolved, 0/1. Correct.
- **Agent pilot:** Claude Code headless (`claude-sonnet-5-5`, `--model sonnet`) on caddy-6115: resolved (1/1, 0
  regressions), QualityScore 100 vs 97 for the reference fix, +10/−6 lines in `selectionpolicies.go`, 4 turns,
  $0.07. This is a pipeline check, not study data.
- **Tests:** custom tasks validate (18/18 local, 3/3 Docker); evaluator, golden, backend and frontend tests pass.

## 3. Important decisions

- Domain-balanced success (mean of per-domain rates) is the headline metric, so bug fixes (113 of 247) cannot
  dominate.
- The core needs regression tests (PASS_TO_PASS ≥ 1), domain confidence ≥ 0.7 and a reference fix with quality
  ≥ 80, and excludes hint or single-test flags.
- Quality measures only what the patch changes (before/after), uses the same scorer for agent and reference, and
  is reported over all patches and over resolved patches.
- All agents get the same tools (read, search, edit, shell) and no web access. Claude Code's headless allow-list
  was widened to `Read,Edit,Write,Glob,Grep,Bash` with `WebFetch,WebSearch` disabled. The prompt says to work
  offline.
- Never mix headless and IDE modes in the study; pin and record each model.

## 4. Pitfalls already hit (check these on a new laptop)

- **SWE-bench scoring only works in WSL/Linux**, not native Windows. Run the app from Ubuntu with Docker Desktop's
  WSL integration on. The WSL copy keeps its own database in `~/.acb/acb.sqlite`.
- **Claude Code must talk to Anthropic directly.** A `~/.claude/settings.json` with `ANTHROPIC_BASE_URL`
  pointing at a local router, or model overrides (for example mapping `haiku` to another vendor's model), gave
  "Unable to connect to API" errors and would make runs not really Claude Code. Keep `env` empty and pass
  `--model`.
- **Claude Code cannot be started from inside a Claude Code session** (the nested call fails). Run agent commands
  in your own terminal.
- **PowerShell `>` writes UTF-16 files**; read agent JSON output with the right encoding.
- The first run of a repository builds its Docker image (several minutes); Pro images are several GB each.

## 5. Environment per laptop (not in git)

Each laptop needs its own:
- `.env`: `ACB_PYTHON`, `ACB_SWEBENCH_PRO_SCRIPTS`, `ACB_EVAL_MODE=docker`
- `~/acb-venv`: `swebench`, `lizard`, `radon`, `bandit`, `ruff`, `pandas`
- `~/SWE-bench_Pro-os` (clone)
- Node 22 in Ubuntu
- Docker Desktop with WSL integration
- each agent's login

Steps: `docs/EVALUATION_GUIDE.md` section A2.

**Results live in each laptop's local database.** To use both laptops for one study:
- Run the same protocol on both, splitting the work (for example by agent).
- Export results on each laptop and commit the export folder.
- Build the paper tables from both exports together:
  `python golden/scripts/score_table.py --input <laptop1 results.csv> <laptop2 results.csv>`
- Never run the same (task, agent, attempt) on both laptops.

## 6. Still to do

1. A second person confirms `golden/configs/core_review.yaml`; report the agreement (kappa).
2. Set up the app in WSL on the laptop(s) that will run the study (Node 22, `.env`).
3. Run the 30-task core × 4 agents (× attempts) with one fixed protocol; export; build the score table.
4. Optional, not started (the owner said "not now"):
   - record cost per run
   - a code-duplication quality check
   - time and cost in the score table
   - a scorer for the 30 Golden test-generation tasks
5. Merge `feat/golden-dataset` into `main` when ready (not done; `main` has only the first commit).
