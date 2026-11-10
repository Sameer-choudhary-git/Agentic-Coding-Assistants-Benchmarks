# How results are evaluated and scored, and the key links

## 1. The two benchmarks

| | Custom suite | SWE-bench Verified |
|---|---|---|
| What | 18 synthetic Python tasks, 3 in each of 6 categories | 12 real GitHub issues from the human-validated SWE-bench Verified set |
| Why | Isolates categories SWE-bench does not (security fixes, test writing, refactoring) and adds quality metrics | The standard benchmark the outline names; comparable with published results |
| Task choice | Written for this project, each validated (starter fails, reference passes) | 4 easy, 4 medium and 4 hard by share of 122 leaderboard submissions that solved each issue (seed 2026), in `swebench_pilot/candidates.json` |
| Workspace | Copy of the task's starter files | `git clone` of the real repository at the issue's base commit, plus `ISSUE.md` |
| Scoring engine | This project's evaluator (`evaluator/`), Docker or local | The official SWE-bench harness (`pip install swebench`), Docker only |
| Default design | 18 tasks × 4 assistants × 2 attempts = 144 runs | 12 tasks × 4 assistants × 1 attempt = 48 runs |

An experiment uses one benchmark. The Tasks, Experiments, Dashboard and Results pages have a benchmark switch, and the two are never pooled in one figure.

## 2. One run, step by step (both benchmarks)

1. **Create workspace.** The app prepares a clean folder outside the project.
2. **Start timer.** The operator gives the assistant the frozen prompt shown on the run page and works through it.
3. **Log as you go.** Every follow-up prompt counts as an iteration, and every manual fix or hint as an intervention.
4. **Stop and submit.** The app snapshots the workspace (custom suite) or builds a patch against the base commit (SWE-bench).
5. **Evaluate.** The evaluator runs, then stores a report, every test outcome and the artifacts.
6. **Results** update from stored records only. Nothing is estimated.

## 3. How a run is scored

**Custom suite.**

- **Acceptance tests:** hidden tests that check the requested behaviour.
- **Regression tests:** hidden tests that check nothing else broke.
- **Success:** every acceptance test passes and no regression test fails.
- **Test-writing tasks:** success instead means the assistant's own tests meet the coverage and mutation-score thresholds.
- **Also recorded, not part of success:**
  - new Ruff lint findings and new Semgrep security findings, against the starter code;
  - files and lines changed;
  - edits outside the allowed paths.

**SWE-bench Verified.**

- **FAIL_TO_PASS:** tests the real fix made pass. All must pass.
- **PASS_TO_PASS:** tests that already passed. All must still pass.
- **Resolved (success):** both conditions hold. This is the harness's own definition, the same one the leaderboard uses.
- **Not resolved:** an empty patch, a patch that does not apply, or any failing test.
- **Not scored:** Ruff and Semgrep don't run on these repositories, because they carry their own existing findings.

**On Windows:** the official SWE-bench harness supports Linux and macOS. Run the backend (or at least the evaluator) inside WSL2 with Docker Desktop's WSL integration turned on. The custom suite works natively on Windows.

**Re-evaluate, don't redo.** If scoring fails because of the tooling (Docker, harness, network), the run page shows **Re-evaluate submission**. It scores the same submission again; time, prompts and interventions stay as recorded, and every evaluation attempt is kept. Use **Retry attempt** only when the session itself went wrong.

**Operational failures are not task results.** Examples are a missing Docker engine, a harness crash or a changed task. The run is marked failed and excluded from success rates until it is re-evaluated.

## 4. How runs become scores

| Metric | Definition |
|---|---|
| Success rate | successful completed runs / completed runs, per assistant (and per category or difficulty) |
| 95% interval | Wilson interval for a proportion; rough, since attempts on one task are not independent |
| Intention-to-treat rate | successes / all planned attempts, so missing runs count against the assistant |
| Time | median and quartiles of wall-clock seconds per completed run |
| Effort | median iterations (follow-up prompts) and human interventions per run |
| Quality (custom suite) | new Ruff and Semgrep findings, regression failures, coverage and mutation score |

- **Effective runs only:** only the latest run of each planned attempt counts. Retries replace earlier runs and are never added to them.
- **Statistical tests:** `analysis/analyze.py` reads the export. It keeps only task × attempt blocks where every assistant has a completed run. On those it runs Cochran's Q across assistants for success, exact McNemar tests between pairs with Holm correction, and a Friedman test on durations. All of these are labelled exploratory.
- **Pilot sample:** the SWE-bench pilot is small (48 runs). Report exact counts, for example "Claude Code 7/12", not percentages alone.

## 5. Secondary evidence in the paper (no runs needed)

- **SWE-bench leaderboard re-analysis** (`analysis/swebench/`): 122 submissions from the official SWE-bench/experiments repository. It gives the trajectory, per-task difficulty, repository effects, scaffold effects, and confirms that none of the four products has a SWE-bench entry as shipped.
- **AIDev re-analysis** (`analysis/aidev/`): PR acceptance by agent and task type from 932,791 agent-authored pull requests. It needs a Hugging Face download.
- **Evidence registry** (`evidence/`): 47 published figures from 25 checked sources, shown on the "Literature evidence" page.

## 6. Key links

**Project files (in this repository)**

- `README.md`: setup and running the app.
- `docs/experimental-protocol.md`: the rules operators follow.
- `docs/metrics-and-data-dictionary.md`: every exported field.
- `docs/next-steps-paper-outline.md`: status against the IEEE outline.
- `paper/main.tex` and `paper/main.pdf`: the paper. `paper/literature-summary.md` summarises the reading list.
- `swebench_pilot/README.md`, `analysis/swebench/README.md` and `analysis/aidev/README.md` cover each part.

**Benchmarks and data**

- SWE-bench: https://www.swebench.com, with code at https://github.com/SWE-bench/SWE-bench
- SWE-bench Verified dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified
- SWE-bench Verified announcement (OpenAI): https://openai.com/index/introducing-swe-bench-verified/
- Leaderboard submissions and results: https://github.com/SWE-bench/experiments
- Harness documentation: https://www.swebench.com/SWE-bench/
- AIDev dataset: https://huggingface.co/datasets/hao-li/AIDev, with code at https://github.com/SAILResearch/AI_Teammates_in_SE3

**Core papers**

- SWE-bench (ICLR 2024): https://arxiv.org/abs/2310.06770
- Closest prior work, task-stratified PR acceptance (MSR 2026): https://arxiv.org/abs/2602.08915
- AIDev dataset paper (MSR 2026): https://arxiv.org/abs/2602.09185
- SWE-Bench+, benchmark validity: https://arxiv.org/abs/2410.06992
- The full checked list is in `evidence/sources.json`, also on the app's Literature evidence page.

**The four assistants (official documentation)**

- GitHub Copilot cloud agent: https://docs.github.com/en/copilot/concepts/coding-agent/about-copilot-coding-agent
- Cursor cloud agents: https://cursor.com/help/ai-features/background-agents
- Claude Code: https://code.claude.com/docs/en/overview
- OpenAI Codex: https://developers.openai.com/codex

**Paper template**

- IEEE conference template, also on Overleaf: https://www.ieee.org/conferences/publishing/templates
