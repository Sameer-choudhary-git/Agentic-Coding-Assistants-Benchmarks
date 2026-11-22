# AgentBench-Golden: A Multi-Domain Golden Dataset and Code-Quality-Aware Evaluation for Agentic Coding Assistants

*Research write-up for the paper "Agentic Coding Assistants: A Comparative Study of GitHub
Copilot, Cursor, Claude Code and Codex". It supplies the methodology for Section III and the
evaluation evidence for Section V. All numbers are reproducible with `python -m agentbench all`;
the tables are generated into `reports/RESULTS.md`, and the figures are in `reports/figures/`.*

---

## 1. Motivation and contributions

Practitioners compare coding agents mainly through one leaderboard: SWE-bench Verified, which
is about 96% bug fixes in 12 Python repositories. Prior work shows that this is not enough:

* The closest prior study (arXiv:2602.08915) finds a **29-point gap between task types** in PR
  acceptance and **no single dominant agent**.
* The SWE-bench+ audit (arXiv:2410.06992) shows that benchmark scores are inflated by
  **solution leakage** and **weak tests**.
* Post-merge studies (arXiv:2601.20109) show that **passing tests does not mean good code**.

This project contributes:

1. **AgentBench-Golden v1.0.0.** A 350-task golden dataset covering 8 task domains, 15 language
   categories and 82 repositories. 85% of the tasks were human-validated upstream. It is built
   from SWE-bench Verified, SWE-bench+, SWE-Bench++, SWE-bench Pro, Multimodal, Multilingual,
   SWE-rebench, and NYU CTF Bench (the CTF benchmark used by EnIGMA).
2. **Automatic quality gates.** The SWE-bench+ findings are turned into reproducible filters and
   applied to 9,000 upstream tasks, of which 4,895 are admitted.
3. **A Code Quality Module.** It compares each patch's code before and after the change
   (lizard, ruff, radon, bandit, plus checks that work in any language) and produces a
   0–100 *QualityScore* and a *quality-adjusted resolve rate*.
4. **An automated evaluation pipeline.** It covers ingestion, gating, classification, sampling,
   quality profiling, evaluation and reporting. A weekly CI job refreshes the dataset.
5. **Evidence from 9 published agent runs** (about 4,250 task outcomes and about 620 analysed
   patches), showing how performance depends on task type, difficulty and code quality.

## 2. Dataset construction (paper §III: Methodology)

### 2.1 Sources

| Source | Role | Upstream rows | Admitted |
|---|---|---:|---:|
| SWE-bench Verified | human-validated Python bug fixes; anchor for leaderboard comparability | 500 | 472 |
| SWE-bench+ (2410.06992) | post-cutoff instances; its audit method drives our gates | 217 | 35 (182 duplicate Verified) |
| SWE-Bench++ | 7 languages, curated `task_type`, `difficulty`, `repo_type` labels | 500 | 425 |
| SWE-bench Pro | long-horizon enterprise tasks with feature, refactor and security labels | 642 | 584 |
| SWE-bench Multimodal | visual/front-end issues with screenshots | 100 (dev) | 88 |
| SWE-bench Multilingual | 9 languages, human-validated | 300 | 284 |
| SWE-rebench | large, continuously mined, LLM-scored pool | 6,542 | 2,808 |
| NYU CTF Bench (EnIGMA) | offensive security: crypto, pwn, rev, web, forensics, misc | 199 | 199 |

### 2.2 Domain taxonomy and classifier

The 8 domains are bug fix, feature implementation, refactoring, performance, security fix,
frontend/visual, test generation and offensive-security CTF. Each task's domain is assigned in
this order of precedence:

1. **Structure.** Multimodal tasks are frontend/visual; NYU CTF tasks are CTF.
2. **Curated upstream labels.** SWE-bench Pro and SWE-Bench++ labels are mapped to domains.
   When a Pro task carries both a bug label and an enhancement label, the bug label wins.
3. **Keywords plus patch shape.** Keyword weights are applied to the issue *prose only*: code
   blocks, URLs and issue-template boilerplate are removed first.

Security is an override, but it needs strong evidence: a score of at least 3 that includes an
unambiguous vulnerability term. Every decision stores its evidence and a confidence value.

Manual spot-checks found two systematic false-positive sources, and both were fixed:

* Template checkboxes such as "This is not a security vulnerability" were triggering the security label.
* Domain jargon was misread, for example "quadratic biases" in a quantum-annealing library.

The `review_sheet.csv` export closes the loop with human annotators.

### 2.3 Quality gates (SWE-bench+ operationalised)

**Blocking gates:**
* missing gold patch or FAIL_TO_PASS tests
* **solution leakage**: two or more non-trivial added lines (25+ characters) appear verbatim in
  the issue, or every candidate line does
* patch too large (more than 600 changed lines or more than 12 files)
* patch touches only tests or docs
* test patch modifies source files
* exact and near-duplicate issues (5-gram Jaccard ≥ 0.8; the higher-priority source is kept)
* SWE-rebench LLM scores above 1 for issue clarity or test quality

**Advisory flags:** weak tests (one FAIL_TO_PASS with a tiny test patch), hints containing
code, possible pre-training contamination.

**Leakage results.** Verified **5.0%**, Multimodal 4.0%, SWE-Bench++ 3.0%, Pro 2.6%,
SWE-rebench 1.9%, Multilingual 0.7%. Our criterion is strict: verbatim code lines only. It
therefore gives a *lower bound* compared with SWE-bench+'s manual analysis, which also counts
natural-language solution descriptions. Over half of SWE-rebench (54.6%) fails its own
LLM-assigned quality scores. This is the clearest case for gating automatically mined data.

### 2.4 Difficulty normalisation

Upstream difficulty labels are not comparable across sources: Verified uses time-to-fix
buckets, SWE-Bench++ uses easy/medium/hard, SWE-rebench uses an LLM score, Pro has a hard
subset, and CTF uses the event tier. For unlabelled tasks we fit a complexity model
(log churn + files + hunks) and set its thresholds to maximise balanced accuracy against
**998 human labels**. The result is balanced accuracy 0.66, **97.6% agreement within one
level**, and Spearman ρ = 0.68. That is good enough for stratification, but not a substitute
for a human label.

### 2.5 Sampling

Sampling is stratified within each domain:

* Strata are (language × difficulty) cells, filled round-robin.
* Human-validated sources are preferred, and each repository is capped at 15% of a domain.
  When few repositories are available the cap relaxes automatically (this was needed for Multimodal).
* **Anchors** guarantee SWE-bench Verified tasks (45 bug fix, 8 feature, 2 performance,
  20 test generation), so results stay comparable with public leaderboards.
* Test-generation tasks are derived SWT-bench-style from held-out validated bug fixes.
  They are never the same instance as a fix task in the set.

### 2.6 Final composition

| Domain | Tasks | Easy/Med/Hard | Main sources |
|---|---:|---|---|
| bug_fix | 110 | 39/37/34 | Verified, Multilingual, Pro |
| feature_implementation | 60 | 22/16/22 | Pro, Verified, Multilingual, SWE-Bench++ |
| refactoring | 30 | 6/11/13 | Pro, SWE-rebench |
| performance | 20 | 4/8/8 | Pro, SWE-Bench++, SWE-rebench, Verified |
| security_fix | 30 | 7/11/12 | Pro, Multilingual (e.g. axios SSRF CVE-2024-39338), SWE-rebench |
| frontend_visual | 25 | 10/8/7 | Multimodal |
| test_generation | 30 | 12/9/9 | Verified, Multilingual (derived) |
| offensive_security_ctf | 45 | 0/20/25 | NYU CTF (EnIGMA) |

Languages: Python 128, JavaScript 67, Go 47, Java 14, Rust 14, TypeScript 11, Ruby 9, C 8,
PHP 7, C++ 6. CTF tasks use binary, web and mixed environments. Gold patches score a mean
QualityScore of **96.9**, which is the human baseline for agent comparison.

### 2.7 Runnable subset and balanced core (for running the four assistants)

The tool study runs assistants on tasks that can be scored by hidden tests in Docker. The app
(`golden/dataset/app_tasks.json`, written by `python -m agentbench export-app`) therefore uses the
golden FAIL_TO_PASS tasks from sources with an executable harness:

| Domain | Runnable (after review) | Reviewed core | Core sources |
|---|---:|---:|---|
| bug_fix | 115 | 5 | Pro 2, Multilingual 2, Verified 1 |
| feature_implementation | 52 | 5 | Multilingual 2, Verified 2, Pro 1 |
| security_fix | 26 | 5 | Pro 4, Multilingual 1 |
| frontend_visual | 25 | 5 | Multimodal 5 |
| refactoring | 17 | 5 | Pro 5 |
| performance | 14 | 5 | Pro 4, Verified 1 |
| **Total** | **249** | **30** | 19 repositories, 7 languages |

Verified, Multilingual and Multimodal tasks are scored by the official `swebench` harness. SWE-bench
Pro tasks are scored in their published images with Pro's run scripts, following Pro's evaluator:
reset to the base commit, apply the patch, apply the hidden test patch, run the selected test files,
and count the task resolved only if every FAIL_TO_PASS and PASS_TO_PASS test passes. CTF (flag match)
and test-generation tasks need separate judges and are reported from the dataset only.

**Why a balanced core.** Running all 249 tasks would weight the result by the source mix (46% bug
fixes), and SWE-bench Verified alone is about 96% bug fixes (§4.3). The core has 5 tasks per domain
(30 tasks; 9 easy, 8 medium, 13 hard; 16 Pro, 5 Multilingual, 5 Multimodal, 4 Verified).

**How the core was selected** (`configs/core_review.yaml`, applied by `export-app`):

1. *Automatic eligibility* (`core_eligible`), stricter than the dataset gates because each core task
   carries 1/30 of the score: no solution-hint or weak-test flag; domain confidence of at least 0.7;
   the reference fix scores at least 80 and applies cleanly to the base commit (checked by the
   code-quality module); at least one FAIL_TO_PASS **and** one PASS_TO_PASS test, so an agent that
   breaks other behaviour fails. This leaves 154 of 249 tasks. The PASS_TO_PASS rule removes 66
   tasks, because SWE-bench Pro ships no regression tests for 313 of its 642 instances.
2. *Manual label review* of all 64 eligible candidates in performance, refactoring, security_fix and
   feature_implementation, plus the bug_fix and frontend_visual picks.
3. *Selection* of five confirmed tasks per domain, spread over difficulty, source, repository and
   language where the confirmed pool allows. Performance has no confirmed medium-difficulty task
   with regression tests, so it has one easy and four hard tasks.

**Label audit finding.** Of the 64 reviewed candidates, **20 (31%) had the wrong domain**. The
errors were concentrated in labels derived from SWE-bench Pro's issue categories: 5 of 9
"performance" and 11 of 19 "refactoring" candidates describe ordinary bugs or features. Security
had 2 of 11 wrong and features 2 of 25. The corrections are applied to the app's tasks. Domain
labels for the remaining (unreviewed) golden tasks should be treated as provisional, and the review
should be confirmed by a second, human annotator (report agreement, e.g. Cohen's κ).

**Headline metric.** Report the **domain-balanced success rate**, the unweighted mean of the
per-domain success rates, next to the raw rate and the per-domain table. Each domain then counts
equally. Precision is limited. At n=5 a per-domain rate has a Wilson 95% CI of about ±33 points,
so per-domain differences between tools are descriptive only. The balanced mean over 30 tasks has
a CI of about ±17 points. Because every tool solves the same tasks, compare tools with paired tests
(McNemar or a paired bootstrap over tasks). These are much more sensitive than comparing two
independent intervals. Run more attempts per task, or more core tasks, if differences under about
15 points matter.

## 3. Code Quality Module (paper §V: post-merge quality; §VI: technical debt)

For a patch at `repo@base_commit`, the module fetches only the touched files, applies the
patch in memory (tolerating line offsets), and compares the code **before and after**.
Measuring the *change* rather than absolute counts means existing debt in the repository is
not blamed on the agent.

| Dimension (cap) | Penalty driver |
|---|---|
| Reliability (25) | 3 points per new ruff finding; 6 points for pyflakes-level defects (undefined names, unused imports, syntax errors) |
| Complexity (20) | 6 points per function pushed past cyclomatic complexity 10; growth of the worst function; long new functions (lizard, 15+ languages) |
| Maintainability (10) | radon maintainability-index drop, scaled down for files that are still highly maintainable |
| Security (30) | 15 points per new bandit finding of medium or high severity; 10 points per insecure pattern (eval/exec, shell=True, TLS verification off, innerHTML, hard-coded secrets, SQL string building, strcpy, unsafe blocks) |
| Hygiene (10) | debug prints, TODOs, commented-out code, **lint suppressions**, broad excepts, **stray scratch files** |
| Size (5) | patch bloat over 2× the gold patch |

**Use in the tool study.** The main app runs the same module on each assistant's patch
(`evaluator/patch_quality.py`). Touched files are read at the base commit from the task workspace's git
history instead of GitHub. The patch-bloat check uses the reference fix's size (`gold_changed_source_lines`
in `dataset/app_tasks.json`), so the reference fix itself never ships with the task. Each run therefore has
QualityScore, the six sub-scores and the reference fix's score on the same scale. The Results page reports
the mean over resolved patches separately from the mean over all patches, because a failed attempt is often
a small patch that scores well. A paired comparison per task (assistant vs reference fix, or assistant vs
assistant) is the recommended analysis. Caveat: radon's maintainability index is noisy on very small files
(a 2-line edit to a 3-line file can lose ~6 points). This affects reference and assistant patches alike,
but it is one reason to compare within a task rather than across tasks.

The module is validated by unit tests on synthetic good and bad patches. On real gold patches
it is conservative: 8 of 275 gold patches score below 80.

## 4. Evaluation evidence (paper §V)

### 4.1 Agents

We used published per-instance outcomes and patches from 9 SWE-bench Verified submissions:

* **Strong-model, bash-only scaffold:** Claude Opus 4.6, GPT-5.1-Codex, Gemini 3 Pro (mini-SWE-agent).
* **Agent frameworks:** OpenHands with Claude Opus 4.5; SWE-agent with Claude 4 Sonnet;
  AutoCodeRover v2.1; Agentless 1.5.
* **Commercial agents:** Amazon Q Developer Agent; Google Jules.

**Caveat:** these are model-plus-scaffold research runs, not the commercial Copilot, Cursor,
Claude Code or Codex CLI products. §6 explains how to close that gap.

A data-integrity issue came up during import. The Gemini 3 Pro submission's
`per_instance_details.json` marks every instance as unresolved. The pipeline detects this and
rebuilds outcomes from 500 per-instance harness reports, giving 70.1% on our admitted pool
against 69.6% officially reported.

### 4.2 Overall resolve rates (Wilson 95% CIs)

| Agent | Verified (admitted, n=472) | Golden Verified subset (n=69) |
|---|---|---|
| OpenHands + Claude Opus 4.5 | **77.5** [73.6–81.1] | 69.6 [57.9–79.2] |
| mini + Claude Opus 4.6 | 75.6 [71.6–79.3] | 66.7 [54.9–76.6] |
| mini + Gemini 3 Pro | 70.1 [65.8–74.1] | 65.2 [53.4–75.4] |
| SWE-agent + Claude 4 Sonnet | 65.9 [61.5–70.0] | 58.0 [46.2–68.9] |
| mini + GPT-5.1-Codex | 65.0 [60.6–69.2] | 58.0 [46.2–68.9] |
| Amazon Q Developer | 64.8 [60.4–69.0] | 59.4 [47.6–70.2] |
| Google Jules (Gemini 2.0 Flash) | 51.1 [46.6–55.5] | 42.0 [31.1–53.8] |
| AutoCodeRover v2.1 | 50.6 [46.1–55.1] | 44.9 [33.8–56.6] |
| Agentless 1.5 | 49.6 [45.1–54.1] | 43.5 [32.4–55.2] |

* **The golden subset is harder.** Every agent scores 5–9 points lower on it than on the full
  pool. Stratified sampling over-represents hard tasks compared with Verified's skew towards
  easy ones.
* **The top two are statistically tied.** OpenHands + Opus 4.5 vs mini + Opus 4.6:
  +1.9 points, paired-bootstrap CI [−1.1, +4.9].

### 4.3 Task-type dependence

**Domain.** Inside Verified, only bug fix (n=455) and feature (n=14) have enough tasks to
compare. The bug-vs-feature gap is small (≤ 8 points, Cramér's V ≤ 0.03), and the feature
sample is too small to support any claim. This is a **finding about the benchmark**:
Verified cannot measure the cross-domain variation that arXiv:2602.08915 reports for real
pull requests. A multi-domain set such as AgentBench-Golden is needed for that.

**Repository and difficulty.** Here variation is large:

* **Repository gaps reach 23–42 points per agent** (Fig. 2b). scikit-learn is easiest for
  everyone (75–93%), while astropy and sphinx are hardest.
* **Rankings change between repositories.** On matplotlib, SWE-agent + Claude 4 Sonnet drops to
  44%, behind GPT-5.1-Codex, Amazon Q and Agentless (50–53%). On xarray, GPT-5.1-Codex (86%)
  beats both Claude agents (81%).
* **Difficulty is the strongest effect** (Fig. 3). Easy-to-hard drops range from **40.5 points**
  (OpenHands + Opus 4.5) to **57.8 points** (Jules).
* **Stronger agents are more robust on hard tasks.** The best agents keep 43–46% on hard tasks,
  while earlier pipelines fall to 9–14%. The spread between agents is about 20 points on easy
  tasks and about 36 points on hard tasks, so **hard tasks separate agents best**.

These results support the paper's claim that **no single number describes an agent**.

### 4.4 Code quality of agent patches

The table below covers the golden Verified subset: 69 tasks, about 620 agent patches.

| Agent | Mean QS (resolved) | Mean QS (unresolved) | Size ratio vs gold (median) | File-localisation F1 | Tests included | Quality-adjusted resolve |
|---|---:|---:|---:|---:|---:|---:|
| Gold (human) | 97.1 | – | 1.00 | – | – | 97.1 |
| OpenHands + Opus 4.5 | 97.8 | 92.6 | 1.00 | 0.78 | 1.4% | 68.1 |
| mini + Opus 4.6 | 97.3 | 93.6 | 1.00 | **0.90** | 0% | 65.2 |
| mini + Gemini 3 Pro | 97.4 | 91.0 | 1.00 | 0.84 | 1.5% | 62.3 |
| SWE-agent + Claude 4 Sonnet | 96.0 | **86.8** | 1.25 | 0.75 | **15.9%** | 56.5 |
| mini + GPT-5.1-Codex | 96.8 | 91.5 | 1.00 | 0.79 | 0% | 56.5 |
| Amazon Q Developer | 96.1 | 94.1 | **1.41** | 0.85 | 0% | 56.5 |
| Jules | 98.9 | 95.8 | 0.75 | 0.81 | 0% | 40.6 |
| AutoCodeRover v2.1 | 98.9 | 97.4 | 0.60 | 0.78 | 0% | 44.9 |
| Agentless 1.5 | 99.1 | 97.2 | **0.52** | 0.82 | 0% | 43.5 |

Findings:

1. **Correct patches are cleaner.** Resolved patches average QS 97.5; unresolved ones average
   93.8. 36% of resolved patches have at least one quality issue, against 50% of unresolved
   ones. A failing patch tends to be messier, not just wrong.
2. **Resolved patches are mostly clean**, but 1–2 per agent fall below the quality bar.
   Quality adjustment lowers resolve rates by 0–3 points and barely changes rankings
   (Kendall τ = 0.89). On this Python-centric subset, tests and code quality mostly agree.
   That fits with post-merge problems (arXiv:2601.20109) coming more from long-term
   maintainability than from defects visible in a single diff.
3. **Different design philosophies show up in patch shape.**
   * *Pipeline agents* (Agentless, AutoCodeRover, Jules) write **minimal** patches, about half
     the size of the gold patch. Their quality is the highest of any group, but they resolve
     the fewest tasks.
   * *Interactive agents* (Amazon Q, SWE-agent) write **larger** patches (1.25–1.41× gold),
     which means more for a human to review.
   * Only SWE-agent regularly adds tests (16%). It also leaves **stray scratch files** in the
     repository root, such as `reproduce_issue.py` and `debug_*.py`. 17 of its 500 Verified
     patches (3.4%) contain them. In the golden subset, just 2 patches carried 22 scratch files
     with 361 `print` calls. This is direct evidence of review burden moving to humans
     (paper §VI).
4. **The most common issues introduced** are long lines, PLR0912 (too many branches),
   PLW2901 (loop variable overwritten), **lint suppressions** (28 instances of
   `# noqa` / `type: ignore` added to silence tools), broad excepts, and **F821
   undefined names** (15). Undefined names are real latent defects that the tests did not catch.
5. **Localisation.** The bash-only Claude Opus 4.6 run edits the right files most precisely
   (F1 0.90). Higher localisation does not guarantee resolution: Agentless reaches F1 0.82
   at a 43.5% resolve rate.

## 5. Automation

| Component | What it automates |
|---|---|
| `python -m agentbench build` | download (SHA-256 manifest) → normalise → classify → gate → calibrate → sample → quality-profile → schema-validate → export JSONL/Parquet/datasheet/review sheet |
| `python -m agentbench evaluate --predictions p.jsonl [--run-harness]` | score any agent: outcomes (via the official `swebench` Docker harness or a supplied results file), QualityScore, localisation, size ratio |
| `python -m agentbench evaluate --published` | import and score published leaderboard runs |
| `python -m agentbench report` | all tables and figures, with Wilson CIs, Cramér's V, a paired bootstrap and Kendall τ |
| `.github/workflows/ci.yml` | lint and unit tests on every push (13 tests) |
| `.github/workflows/golden-refresh.yml` | weekly rebuild and re-evaluation; opens a PR when upstream data or results change |

## 6. Limitations and threats to validity (paper §VI)

* **Tools vs models.** The published runs are model-plus-scaffold research systems, not the
  commercial products. For the paper's four-tool comparison, run Copilot agent, Cursor
  background agent, Claude Code (headless `claude -p`) and Codex CLI on the golden set. Export
  each tool's diffs as SWE-bench-format predictions and score them with
  `evaluate --predictions --run-harness`. The pipeline needs no other changes.
* **Execution coverage.** The published-agent outcomes in §4 come from published harness results
  on Verified. The app scores Verified, Multilingual, Multimodal and Pro tasks (§2.7); the Pro scorer
  follows Pro's evaluator and has been tested end to end with a stand-in container, but should be
  checked on one real Pro task before the full study. SWE-Bench++, SWE-rebench, CTF and
  test-generation tasks need their own judges and are not run in the app.
* **Domain labels** for non-curated sources are heuristic, with confidence of at least 0.5
  required. Human adjudication through `review_sheet.csv` is recommended before publication.
* **Quality-module scope.** Lint and security analysis is deepest for Python. Other languages
  get complexity (lizard), smells and insecure-pattern checks. The penalty weights are expert
  priors, not fitted values; the sub-scores are reported so others can re-weight them.
* **Contamination.** Most Verified and SWE-rebench tasks predate current model training
  cutoffs (flagged `possible_contamination`). The weekly refresh can bring in post-cutoff
  SWE-rebench and SWE-bench-Live tasks.
* **Statistical power.** The golden subset per agent is n=69, so its CIs span about ±11 points.
  Claims that need precision use the 472-task admitted pool.

## 7. Suggested text for the paper

* **§III Methodology.** Use §§2.1–2.5, the datasheet (`dataset/DATASHEET.md`) and Fig. 1.
* **§V Evaluation evidence.** Use §4.2 for benchmark performance, §4.3 with Figs. 2b and 3 for
  task-type dependence, and §4.4 with Fig. 4 for post-merge quality.
* **§VI Risks.** Use the stray-file and lint-suppression findings (review burden, technical
  debt), the leakage rates (benchmark-to-practice gap) and the security-pattern detector
  (security of agent code).
