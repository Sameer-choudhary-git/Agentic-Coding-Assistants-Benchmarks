# Evaluating coding agents with the Golden benchmark

This guide covers the whole study: setup, running each agent on the same tasks, scoring, the final score table, and
the logic and design decisions behind each step. Part A is the how-to. Part B explains how everything works, for
the paper's method section.

---

# Part A — Running a study

## A1. What you get

For every **(task, agent, attempt)** run, the platform records:

| Measure | How it is decided |
|---|---|
| **Resolved** (yes/no) | The task's hidden tests run in Docker: every FAIL_TO_PASS test (the ones the real fix makes pass) must pass, and every PASS_TO_PASS test (existing behaviour) must still pass. |
| **QualityScore** (0–100) | The code quality module: the problems the patch adds (lint, complexity, maintainability, security, hygiene, size), compared with the code before the patch. |
| **Reference QualityScore** | The real upstream fix's score on the same scale, for comparison. |
| Time, follow-up prompts, interventions, diff size | Recorded by the app during the run. |

At the end, `golden/scripts/score_table.py` turns the export into the paper's score table (section A7).

## A2. One-time setup (Windows 11 + WSL2)

SWE-bench's harness only runs on Linux, so **the app and the scoring run inside WSL (Ubuntu)**. Docker Desktop
provides the Docker engine.

1. **Docker Desktop:** Settings → Resources → WSL integration → turn on *Ubuntu* → Apply & restart. Check from
   Ubuntu: `docker info`.
2. **Python environment in Ubuntu** (this setup has already been done on this machine):
   ```bash
   python3 -m venv ~/acb-venv
   ~/acb-venv/bin/pip install "swebench>=4" datasets lizard radon bandit ruff requests pyyaml jsonschema pandas
   git clone --depth 1 https://github.com/scaleapi/SWE-bench_Pro-os ~/SWE-bench_Pro-os
   ```
3. **Node 22 in Ubuntu** (needed to run the app there):
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs
   ```
4. **`.env`** in the project root (copy it from `.env.example`). Replace `<you>` with your Ubuntu user name:
   ```ini
   ACB_PYTHON=/home/<you>/acb-venv/bin/python
   ACB_SWEBENCH_PRO_SCRIPTS=/home/<you>/SWE-bench_Pro-os/run_scripts
   ACB_EVAL_MODE=docker
   ACB_ENABLE_AUTOMATION=0      # 1 only if you let the app start headless agents itself
   ```
5. **Start the app from Ubuntu.** Stop any Windows copy first, because both use ports 4000 and 5173:
   ```bash
   cd /mnt/d/Shinchan/agentic-coding-benchmark/agentic-coding-benchmark/agentic-coding-benchmark
   npm install && npm run dev        # app: http://localhost:5173
   ```
   The WSL copy keeps its own database in `~/.acb/acb.sqlite`.
6. **Agents.** Install and log in to each agent you will compare: Claude Code (`claude`), Codex (`codex`), Cursor
   (`cursor-agent`), GitHub Copilot (VS Code agent mode or `copilot`). For Claude Code, `~/.claude/settings.json`
   must not route requests through a proxy or override the model. Otherwise the run is not really Claude Code.

### Check that scoring works (about 10 minutes)

Run the reference fix of one task per source through the real scorer. Every row must say `"outcome": "passed"`.
With `--negative`, a patch that changes nothing must say `acceptance_failed`.

```bash
cd /mnt/d/.../agentic-coding-benchmark
ACB_SWEBENCH_PRO_SCRIPTS=~/SWE-bench_Pro-os/run_scripts ~/acb-venv/bin/python golden/scripts/smoke_harness.py \
  --negative caddyserver__caddy-6115 NodeBB__NodeBB-97c8569a79 diegomura__react-pdf-1280 django__django-16801
```

Result on 2026-11-24: all four reference fixes resolved, with quality equal to the stored reference score. Both
negative controls failed, as they should.

## A3. Decide the protocol before the first run

These choices must be the same for every agent, and the paper must report them:

| Decision | Recommendation |
|---|---|
| Task set | **Golden balanced core**: 30 tasks, 5 in each of 6 domains (`golden/configs/core_review.yaml`). |
| Attempts per task | 1 is the minimum; 2–3 if your budget allows (non-deterministic agents). |
| Mode | **All headless** or **all IDE (human-operated)**. Never mix modes between agents. |
| Model | Pin it and record it, e.g. `--model sonnet` for Claude Code. Use the vendor's default model only if you name it. |
| Prompt | The frozen prompt the app generates (identical for every agent). |
| Time limit | 30 minutes per run (the app default for SWE-bench/Golden tasks). |
| Tools | Read, search, edit and shell in the workspace. **No web access**: the upstream fix of a public issue is one search away. |
| Order | Use the app's randomised run order ("Open next run in order"). |

## A4. Create the experiment

App → **Experiments → New** → benchmark **Golden**. The 30-task balanced core is pre-selected → select the agents
→ set attempts → *Review and create* → *Start experiment*.

The planned matrix is tasks × agents × attempts, e.g. 30 × 4 × 1 = 120 runs. Every run is recorded, including
failed, retried and invalidated ones.

## A5. Run each attempt

Click **Open next run in order**, then:

1. **Create workspace.** The task's repository is cloned at the commit before the real fix, and the issue is
   written to `ISSUE.md`.
2. **Start session timer**, then **Copy frozen prompt**.
3. Run the agent in that folder only.
   - **IDE mode** (Copilot, Cursor): open the folder, start a new agent chat, paste the prompt.
   - **Headless mode:**

     | Agent | Command (prompt = contents of `ISSUE.md`) |
     |---|---|
     | Claude Code | `claude -p "<prompt>" --model sonnet --permission-mode acceptEdits --allowedTools "Read,Edit,Write,Glob,Grep,Bash" --disallowedTools "WebFetch,WebSearch" --output-format json` |
     | Codex | `codex exec --sandbox workspace-write --skip-git-repo-check "<prompt>"` |
     | Cursor | `cursor-agent -p --force --output-format text "<prompt>"` |
     | Copilot | `copilot -p "<prompt>" --allow-all-tools -s` |

     With `ACB_ENABLE_AUTOMATION=1`, the run page's **Run headless CLI instead** button runs these for you and
     stores the agent's output.
4. Log every extra prompt you send as **Log follow-up prompt**, and every manual edit or approval as **Log
   intervention**.
5. **Stop timer**, then **Submit and evaluate**. Scoring takes about 2–8 minutes per task; the first build of each
   repository's Docker image takes longer.
6. If the environment broke (not the agent's fault), use **Mark operational failure** and then **Retry attempt**.
   If the protocol was broken (web search, wrong model), use **Invalidate run**.

Each run page shows the test outcomes and a **Patch code quality** panel with the score, the reference fix's score,
the sub-scores and each finding.

## A6. Watch progress

The **Results** page with **Golden** selected shows:
- success per agent and per domain
- the **domain-balanced success rate**
- the **Code quality of the patches** table: the mean over all patches, the mean over resolved patches, the
  difference from the reference fix, and the six sub-scores

## A7. Final score table

1. Export: the **Exports** page, or `npm run export -- <experiment-id>`. This writes
   `artifacts/exports/<stamp>-<id>/results-<id>.csv`.
2. Build the tables:
   ```bash
   python golden/scripts/score_table.py --input artifacts/exports/<stamp>-<id>/results-<id>.csv --out analysis/score_table
   ```
3. `analysis/score_table/score_table.md` (plus one CSV per table) contains:

| Table | Content |
|---|---|
| 1. Main results | Per agent: completed, resolved, success % [Wilson 95% CI], **domain-balanced success** [bootstrap 95% CI], mean QualityScore (all / resolved), difference from the reference fix, regression failures |
| 2. By domain | Resolved / completed per agent and domain |
| 3. Quality sub-scores | Mean reliability, complexity, maintainability, security, hygiene, size |
| 4. Pairwise | Each pair of agents on the same task and attempt: exact McNemar p-value (Holm-corrected), mean paired quality difference [bootstrap CI] |

The headline result is **domain-balanced success** plus **quality on resolved patches**. Treat per-domain numbers
as exploratory: 5 tasks per domain is a small sample.

`npm run analyze -- --input <results csv> --out analysis/output` adds the platform's general report: missing data,
durations, iterations, Cochran's Q and Friedman tests.

## A8. Checklist before the results go in the paper

- [ ] A second person confirmed `golden/configs/core_review.yaml` (the 30 picks and 20 label corrections). Report
      their agreement (Cohen's kappa).
- [ ] Every agent ran in the same mode, with a pinned and recorded model, the same prompt, time limit and tools,
      and no web access.
- [ ] Runs with protocol violations are invalidated, not deleted.
- [ ] The smoke test (A2) passed on the machine that scored the study.
- [ ] The limitations in section B10 are stated.

---

# Part B — How it works (logic, decisions and key code)

## B1. Architecture

```
golden/ (Python, offline)                      the app (React + Express + SQLite)            evaluator/ (Python)
  sources -> gates -> classifier -> difficulty     Tasks / Experiments / Runs / Results          swebench.py: workspace + scoring
  -> sampler -> code quality -> export             runService ingests report.json               patch_quality.py: QualityScore
  dataset/golden_v1.0.0.jsonl (350 tasks)          resultsService: aggregates, domain-balanced   Docker: SWE-bench harness / Pro images
  dataset/app_tasks.json (249 runnable, core)  ->  exportService: CSV/JSONL               ->     golden/scripts/score_table.py
```

## B2. Golden dataset construction (`golden/agentbench`)

**Sources** (`configs/golden.yaml`), 9,000 candidates in total:

| Source | Candidates |
|---|---|
| SWE-bench Verified | 500 |
| SWE-bench++ | 500 |
| SWE-bench+ | 217 |
| SWE-bench Pro | 642 |
| SWE-bench Multimodal | 100 |
| SWE-bench Multilingual | 300 |
| SWE-rebench | 6,542 |
| NYU CTF | 199 |

All are normalised to one schema (`schema.py`: `GoldenTask`).

**Quality gates** (`gates.py`). A failing hard gate rejects the task; 4,895 tasks are admitted:

| Gate | Rule |
|---|---|
| Solution leak (SWE-bench+ method) | ≥ 2 added lines of ≥ 25 characters from the fix appear verbatim in the issue |
| Problem length | 120 – 20,000 characters |
| Patch size | ≤ 600 changed lines and ≤ 12 files |
| Test patch touches source | rejected |
| Docs-only or tests-only fix | rejected |
| Near-duplicate | Jaccard ≥ 0.80 on 5-word shingles; the higher-priority source is kept |
| SWE-rebench quality | issue-text and test scores ≤ 1 |

Advisory flags are kept on the task rather than rejecting it: `solution_hint_partial`, `weak_tests_single_f2p` (one
deciding test), `hints_contain_code`, and `possible_contamination` (created before 2024-06-01).

**Domain classifier** (`taxonomy.py`): rules that record their evidence, not a model. The first rule that applies wins:

1. **Structural:** NYU CTF → `offensive_security_ctf` (confidence 1.0); Multimodal → `frontend_visual` (0.95).
2. **Security override:** weighted keywords (CVE, XSS, injection, traversal, auth bypass…) plus Pro's security tags.
   A score ≥ 3 with a clear vulnerability term → `security_fix`.
3. **Curated labels:** SWE-bench Pro `issue_specificity` and SWE-bench++ `task_type`, mapped to domains (0.85). If
   the keywords strongly disagree, the confidence drops to 0.6.
4. **Keywords + patch shape:** keyword scores per domain. A fix that adds new files or definitions favours
   *feature*. Performance and refactoring need clear evidence. Otherwise the task falls back to `bug_fix` (about
   85% of SWE-bench issues are bug reports).

**Difficulty** (`difficulty.py`): use the source's human label where there is one. Otherwise compute
`complexity = ln(1+changed) + 0.6·ln(1+(files−1)) + 0.35·ln(1+(hunks−1))`. Two thresholds (4.2, 5.6) were fitted on
998 human-labelled tasks:

| Agreement with human labels | Value |
|---|---|
| Exact | 60% |
| Within one tier | 98% |
| Spearman ρ | 0.68 |

**Sampling** (`sampler.py`): domain quotas give **350 tasks**:

| Domain | Quota |
|---|---|
| Bug fix | 110 |
| Feature | 60 |
| Refactoring | 30 |
| Performance | 20 |
| Security | 30 |
| Frontend | 25 |
| Test generation | 30 |
| CTF | 45 |

- Within a domain the sampler stratifies by language, difficulty and source.
- SWE-bench Verified "anchors" keep the set comparable with public leaderboards.
- Seed 20261121.

## B3. From 350 to the runnable set and the balanced core (`golden/agentbench/app_export.py`)

**Runnable in the app: 249 tasks**, shown as 247 (2 are already in the 12-task SWE-bench pilot). These are the
fail-to-pass tasks from sources with a scorer the app can run:

| Source | Scorer | Tasks |
|---|---|---|
| SWE-bench Verified | official harness | 69 |
| SWE-bench Multilingual | official harness | 46 |
| SWE-bench Multimodal | official harness | 25 |
| SWE-bench Pro | Pro's Docker images and scripts | 109 |

Left out: CTF (scored by flag match), test generation (needs a different judge), and SWE-bench++ / SWE-rebench
(no published harness).

**Core eligibility** is stricter than the gates, because each core task carries 1/30 of the score:

```python
def core_eligible(e) -> tuple[bool, str]:
    if set(e["gate_flags"]) & {"solution_hint_partial", "weak_tests_single_f2p"}: return False, "advisory gate flag"
    if (e.get("domain_confidence") or 0) < 0.7:                return False, "uncertain domain label"
    if e.get("gold_quality_score") is None or e["gold_quality_score"] < 80:
                                                               return False, "reference fix below the quality bar"
    if not e.get("gold_patch_applies"):                        return False, "reference fix not verified against the base commit"
    if e["fail_to_pass_count"] < 1:                            return False, "no FAIL_TO_PASS test"
    if e["pass_to_pass_count"] < 1:                            return False, "no PASS_TO_PASS (regression) tests"
    return True, ""
```

154 of 249 tasks are eligible. The main exclusion: 66 Pro tasks ship no regression tests.

**Manual review** (`golden/configs/core_review.yaml`):
- Every eligible candidate in the small domains, and every pick, was read to confirm its domain.
- **20 of 64 automatic labels were wrong** (refactoring 11/19, performance 5/9). They are corrected in
  `label_corrections`, which changes the domain the app shows and scores.
- 5 confirmed tasks per domain were picked, spread over difficulty, source, repository and language.
- The export re-checks each pick: it exists, it is in that domain, it passes `core_eligible`, and each domain has
  exactly 5. Otherwise the build stops.
- Without the review file, `pick_core` makes a seeded choice instead: round-robin easy → medium → hard,
  preferring an unused repository, then an unused source, then human-validated, then not contaminated.

| Domain | Core tasks (source, language, tier) |
|---|---|
| Bug fix | element-web-ce554276db (Pro JS easy), faker-2970 (Ml Ruby easy), NodeBB-84e065752f (Pro JS med), vuejs-core-11739 (Ml TS med), sympy-14248 (Ver Py hard) |
| Feature | tokio-6724 (Ml Rust easy), sphinx-8035 (Ver Py med), NodeBB-05f2236193 (Pro JS med), scikit-learn-25102 (Ver Py hard), micropython-12158 (Ml C hard) |
| Refactoring | qutebrowser-44e64199ed (easy), element-web-27139ca68e (med), ansible-379058e10f, element-web-d06cf09bf0, openlibrary-3aeec6afed (hard) — all Pro |
| Performance | django-16801 (Ver Py easy), NodeBB-767973717b, ansible-3b823d908e, flipt-15b76cada1 (Go), qutebrowser-c09e1439f1 (Pro, hard) |
| Security fix | caddy-6115 (Ml Go easy), NodeBB-97c8569a79 (Pro JS easy), ansible-a20a527014 (med), ansible-5260527c4a, webclients-5174262583 (Pro, hard) |
| Frontend/visual | react-pdf-1280, p5-js-3709 (easy), wp-calypso-35531, react-pdf-2400 (med), wp-calypso-21977 (hard) — all Multimodal JS |

## B4. Workspace and prompt (`evaluator/swebench.py`)

`create_workspace` clones `github.com/<repo>`, checks out `base_commit`, writes `ISSUE.md` and excludes it from the
diff. Every agent gets the same frozen prompt:

```text
You are working in a checkout of the {repo} repository at commit {base_short}.

Resolve the GitHub issue below by changing the repository's source code. Do not modify or add tests unless
the issue explicitly asks for it; hidden tests will be run afterwards. Do not commit; leave your changes in
the working tree. Work offline: do not search the web or look up how the issue was fixed upstream. The issue
text is also saved in ISSUE.md in the repository root.

<issue>
{problem_statement}
</issue>
```

The submission is `git add -A && git diff --cached --binary <base_commit>`, which includes new files. The
issue-text hash is checked on load, so an edited task cannot be scored silently.

## B5. Correctness scoring

- **Verified / Multilingual / Multimodal:** the official `swebench.harness.run_evaluation` runs with the task's own
  dataset (`princeton-nlp/SWE-bench_Verified` or `SWE-bench/SWE-bench_Verified`, `SWE-bench/SWE-bench_Multilingual`,
  `SWE-bench/SWE-bench_Multimodal`) and split (`test`, or `dev` for Multimodal). The harness builds the
  environment, applies the patch and the hidden test patch, and runs the tests.
- **SWE-bench Pro** (`run_pro`) follows Pro's own evaluator in the task's published image:
  ```bash
  cd /app && git reset --hard $BASE && git checkout $BASE
  git apply -v /workspace/patch.diff          # agent's patch; failure => patch_failed
  cp /workspace/test_patch.patch /tests/      # hidden tests
  <last line of before_repo_set_cmd>          # applies the test patch
  bash run_script.sh <selected test files>; python parser.py ... output.json
  ```
- **Rule (both scorers):** resolved = the patch applied **and** every FAIL_TO_PASS passed **and** every
  PASS_TO_PASS passed.
- **Outcomes:** `passed`, `acceptance_failed`, `regression_failed`, `patch_failed`, `empty_patch`.
- **Harness problems** (Docker down, image missing) are `evaluator_error`. They are never counted as a failure of
  the agent.

## B6. Code quality module (`golden/agentbench/code_quality`, `evaluator/patch_quality.py`)

**Principle:** score only what the patch **changes**. Each touched source file is read at the base commit (from the
workspace's git history: `git show <base>:<path>`), the patch is applied in memory, and the before/after versions
are compared. Existing problems in the repository are never charged to the agent. Test and doc files are left out.
Nothing is executed.

| Dimension (cap) | Penalty | Tool |
|---|---|---|
| Reliability (25) | 3 per new lint finding; 6 for defect-level ones (undefined names, unused imports, syntax errors) | ruff |
| Complexity (20) | 6 per function pushed past cyclomatic complexity 10; 1.5 × (growth of the worst function − 3); 3 per new function > 60 lines | lizard (15+ languages) |
| Maintainability (10) | maintainability-index drop: 1.5 × (drop − 1) if the file ends below MI 50, else 0.5 × (drop − 3) | radon (Python) |
| Security (30) | 15 per new medium/high bandit finding; 10 per insecure pattern on added lines (eval/exec, `shell=True`, unsafe deserialisation, weak hashes, TLS verify off, `innerHTML`, hard-coded secrets, SQL string building, `strcpy`/`gets`, `unsafe {}`) | bandit + regex |
| Hygiene (10) | debug print 3, TODO 2, commented-out code 2, lint suppression 4, broad `except` 4, line > 120 characters 0.25, stray scratch file (`reproduce_*.py`, `debug_*`…) 5 | regex |
| Size (5) | 2.5 × log2(patch size ÷ reference size) when more than 2× the reference fix | diff |

```text
penalty_d    = min(raw_penalty_d, cap_d)
QualityScore = max(0, 100 − Σ penalty_d)        # 100 = no new problem found
sub-score_d  = 100 × (1 − penalty_d / cap_d)
```

- The reference fix is scored the same way (`gold_quality_score`). The app stores only its **size**
  (`gold_changed_source_lines`), so the fix itself never ships with the task.
- Missing tools give status `unavailable`, never a score.
- Validation: unit tests on synthetic clean and sloppy patches. On real reference fixes, only 8 of 275 score
  below 80. The app's scorer reproduced the stored reference scores exactly (97.0 and 100.0) in the smoke test.

## B7. Metrics

| Metric | Definition |
|---|---|
| Success rate | resolved ÷ completed effective runs (latest run per planned attempt that finished evaluation). Wilson 95% CI. |
| Intent-to-treat rate | resolved ÷ planned attempts (missing runs count as failures). |
| **Domain-balanced success** | mean over domains of each domain's success rate. Prevents the largest domain from dominating. Bootstrap CI stratified by domain. |
| Quality (all / resolved) | mean QualityScore of scored patches; the **resolved-only** mean is the fair comparison, because failed attempts are often small and look clean. |
| Quality vs reference | mean(agent score − reference fix score) on the same tasks. |
| Pairwise | exact McNemar on discordant pairs (one agent resolved, the other not), Holm-corrected; paired bootstrap for quality differences. |

## B8. Key design decisions

| Decision | Why |
|---|---|
| Reuse public, human-validated benchmarks instead of writing tasks | Real issues, real tests, comparable with leaderboards. |
| Hard gates + advisory flags | Remove broken tasks (leaks, oversized fixes, bad tests) without losing coverage; flags stay visible for analysis. |
| Rule-based classifier with recorded evidence | Every label is explainable and auditable; no LLM labels the data it is used to judge. |
| Manual review of core labels | Source labels are noisy (20/64 wrong); the core carries the headline score. |
| 5 tasks per domain | Equal weight per domain. 30 tasks × 4 agents stays affordable; the cost is wide per-domain intervals. |
| Regression tests required in the core | Without PASS_TO_PASS, a patch that breaks existing behaviour could still count as resolved. |
| Official harnesses for scoring | No custom test logic to defend; the same rule as published SWE-bench results. |
| Quality on the diff, not the file | Fair across repositories with very different existing code. |
| Same quality scorer for agent and reference fix | Gives a meaningful baseline ("as clean as the human fix?"). |
| Quality scored even when Docker fails | A setup problem never loses the quality measure. |
| Equal tool access, no web access | Fair comparison, and no looking up the upstream fix. |
| Pinned seeds, hashes, frozen prompts, append-only run history | Reproducible, auditable results. |

## B9. Where things are

| Path | What |
|---|---|
| `golden/agentbench/` | Dataset pipeline: `sources.py`, `gates.py`, `taxonomy.py`, `difficulty.py`, `sampler.py`, `code_quality/`, `app_export.py` |
| `golden/configs/golden.yaml`, `core_review.yaml` | Build settings; reviewed core and label corrections |
| `golden/dataset/` | `golden_v1.0.0.jsonl/.parquet` (350), `app_tasks.json` (249 + core), `manifest.json`, `DATASHEET.md` |
| `golden/scripts/` | `smoke_harness.py` (scoring check), `score_workspace.py` (score one workspace), `score_table.py` (paper tables) |
| `golden/reports/RESEARCH_REPORT.md` | Full method write-up and published-agent analysis |
| `evaluator/swebench.py`, `evaluator/patch_quality.py` | Workspace, prompt, harness and Pro scoring; patch quality |
| `backend/src/services/` | `runService` (run lifecycle, report ingest), `resultsService` (aggregates), `exportService`, `adapters/` (headless commands) |
| `frontend/src/pages/` | Experiments, RunDetail (quality panel), Results (domain-balanced and quality tables), Golden |
| `docs/assistant-integrations.md` | Headless commands, tool parity, web-access caveats |

Rebuild the app task file after editing `core_review.yaml`: `cd golden && python -m agentbench export-app`, then
press *Synchronise tasks* in the app.

## B10. Limitations to state in the paper

- **Small sample:** 5 tasks per domain gives about ±33 points per domain; the domain-balanced mean over 30 tasks
  is about ±17 points. Use paired tests and report the intervals.
- **AI-assisted curation:** the dataset and core were built and reviewed with an AI assistant (Claude), and Claude
  Code is one of the agents compared. A human confirmation of the core is required.
- **Contamination:** public SWE-bench issues and fixes may be in the models' training data (flagged as
  `possible_contamination`).
- **Performance domain:** 1 easy and 4 hard tasks, and "performance" is checked by the tests' correctness, not by
  timing.
- **Quality score is a heuristic:** maintainability (radon) is Python-only and noisy on tiny files; compare per
  task.
- **Web access:** blocked for Claude Code and Codex by flags. Copilot and Cursor rely on the prompt instruction
  unless the network is blocked at the system level.
- **Headless and IDE modes are different products:** report the mode, and never mix modes within the study.
- **Harness coverage:** each source's scorer was checked with a reference fix and a negative control, not on every
  task. Tasks whose environment fails are `evaluator_error`, not agent failures.
