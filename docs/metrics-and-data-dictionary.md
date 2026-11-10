# Metrics and data dictionary

All metrics are computed from persisted run and evaluation records by
`backend/src/services/resultsService.ts` (web app) and `analysis/analyze.py` (offline analysis).
Both use the same definitions below. Nothing is estimated, imputed or filled in.

## Units of analysis

| Term | Definition |
|---|---|
| Planned attempt | One cell of the experiment matrix: (task, assistant, attempt number). The full design has 18 × 4 × 2 = 144. Planned attempts are **not** results. |
| Run | One execution of a planned attempt. A retry creates a new run (`run_number` 2, 3, …) linked by `retry_of_run_id`; the earlier run is kept unchanged. |
| Effective run | The latest run of a planned attempt. Only effective runs enter aggregates. Retries are allowed only after an operational failure or invalidation, so a measured task failure can never be replaced by a retry. |
| Completed (eligible) run | An effective run whose status is `completed`, i.e. evaluation finished and produced a verdict. |

## Run states

`planned` → `ready` (workspace created) → `running` (session timer started) → `awaiting_human`
(timer stopped, waiting for the operator to submit) → `submitted` → `evaluating` → `completed`.
Side exits: `failed` (operational failure) and `invalidated` (protocol violation). Transitions not
in this graph are rejected by the API with HTTP 409.

## Failure classes

| Class | Meaning | Counted in success rate? |
|---|---|---|
| `task_failure` | Evaluation completed; the submission did not meet the success rule. | Yes, as not passed |
| `timeout` | Evaluation completed, but the session exceeded the time limit. | Yes, as not passed |
| `evaluator_error` | The evaluator could not produce a verdict (tool missing, Docker unavailable, task hash mismatch, crash). | No; re-evaluate after fixing |
| `adapter_error` | A headless CLI adapter failed to run (exit code ≠ 0, not found, auth failure). | No; retry |
| `environment_error` | Operator-reported machine or tool outage unrelated to the assistant. | No; retry |
| `operator_abort` | Operator stopped the run for a documented reason. | No; retry |
| invalidated | Protocol violation (wrong prompt, contaminated workspace, wrong assistant). | No; retry |

Inside an evaluation, `outcome` distinguishes `acceptance_failed`, `regression_failed`,
`test_timeout` (hidden tests did not finish, e.g. an infinite loop in submitted code — a task
failure), `collection_error` (tests could not import the submission — a task failure) and
`evaluator_error`.

## Functional completion

**Success rule (per run).** A run succeeds when all of the following hold:

1. every hidden acceptance check passed — none failed, errored or is missing compared with the
   count recorded at task validation, and at least one passed;
2. no hidden regression test failed or errored;
3. the hidden tests finished within the task's test timeout;
4. the assistant session (`wall_clock_seconds`) did not exceed the attempt's time limit.

Rules 1–3 are applied by the evaluator (`evaluation_success`); rule 4 is applied by the platform
(`success`). Static-analysis findings never change success.

For test-writing tasks, the four acceptance checks are: the submitted suite passes on the original
module; at least `min_tests` tests are collected; line coverage of the target module ≥
`min_line_coverage`; at least `min_mutation_score` of the hidden mutants make the suite fail.

**Success rate** (primary metric) per group *g*:

    success_rate(g) = (# completed effective runs in g with success = true) / (# completed effective runs in g)

with a Wilson 95% score interval. Runs that never completed evaluation are excluded from the
denominator and reported separately as missing data (`not started`, `in progress`, `operational
failures`, `invalidated`).

**Intent-to-treat rate** (sensitivity metric): successes / planned attempts, i.e. every attempt that
did not produce a passing result counts as not passed. Report it alongside the primary rate when
missing data is not negligible.

**Acceptance tests passed / eligible** is reported per run (`acceptance_passed` /
`acceptance_expected`). Counts differ between tasks (parametrised tests), so they are *not*
averaged across tasks; use them for diagnosing individual runs.

**Regression failures**: number of completed runs with `regression_failure = true`, over completed
runs that have regression tests (test-writing tasks have none).

## Efficiency

| Metric | Definition |
|---|---|
| Wall-clock duration | `ended_at − started_at` of the assistant session in seconds. Evaluation time is excluded. Reported as median and inter-quartile range (and mean), because durations are skewed. |
| Iterations | Number of prompts sent to the assistant, including the first one. Automated runs record 1. |
| Human interventions | Number of human actions other than sending a prompt: approving a permission/tool request, editing code by hand, giving a hint not contained in the frozen prompt, restarting or reconfiguring the tool. See the protocol for examples. |
| Operational failures and timeouts | Counts per assistant, from the failure classes above. |

## Code quality

* **Ruff findings** with the fixed configuration `evaluator/config/ruff.toml` (rule families E, F, W,
  B, C90 complexity > 10, S security, SIM). Reported as total findings in the submission and *new*
  findings relative to the unmodified starter code. Matching ignores line numbers: a finding is new
  if its (file, rule, message) occurs more often than in the starter.
* **Changes outside scope**: files changed outside `scope.allowed_paths` (e.g. editing a protected
  module in a test-writing task). Protected files are restored before grading.
* Complexity is only reported through Ruff's C901 rule; no other maintainability index is computed.

## Security

* **Semgrep findings** with the offline rule file `evaluator/config/semgrep/rules.yml` (SQL built by
  string formatting, unsafe deserialisation, eval/exec, shell injection, non-constant-time MAC
  comparison, weak hashes, insecure temp files). Reported as baseline (starter), submission, *new*
  (introduced) and *resolved* findings.
* If Semgrep is not installed or fails, the status is `unavailable` or `error` and the value is
  `null`. It is never treated as zero findings, and such runs are excluded from security
  denominators (the count of excluded runs is reported).

## Reproducibility metadata

Every run records the task id, task version, test version, task hash and prompt hash frozen when the
experiment was created; assistant version (and whether it was detected or typed by the operator, or
unknown); model if known; attempt and run number; execution mode; evaluation mode; evaluator
version and tool versions; operator and machine id; all timestamps; the submission snapshot hash;
and a full event history.

## Exported fields (results CSV / JSONL)

Generated from `DATA_DICTIONARY` in `backend/src/services/resultsService.ts`; also downloadable
from the Exports page.

| Field | Type | Description |
|---|---|---|
| `experiment_id` | uuid | Experiment identifier. |
| `experiment_name` | string | Human-readable experiment name. |
| `planned_attempt_id` | uuid | One cell of the experiment matrix (task × assistant × attempt number). |
| `run_id` | uuid | One execution of a planned attempt. Retries create new run ids; history is never overwritten. |
| `run_number` | int | 1 for the original run, 2+ for retries of the same planned attempt. |
| `retry_of_run_id` | uuid|null | Run that this run retries (only operational failures or invalidated runs can be retried). |
| `is_effective_run` | bool | True for the latest run of each planned attempt; only effective runs enter aggregate metrics. |
| `task_id` | string | Benchmark task identifier, e.g. BF-01. |
| `task_category` | enum | bug_fixing \| feature_implementation \| security_remediation \| refactoring \| test_writing \| repository_reasoning. |
| `task_difficulty` | enum | easy \| medium \| hard (criteria in docs/experimental-protocol.md). |
| `task_kind` | enum | standard (hidden acceptance tests) or test_writing (coverage + mutation checks). |
| `task_version` | semver | Task metadata version. |
| `test_version` | semver | Hidden test-suite version. |
| `task_hash` | sha256 | Hash of task.json, prompt, starter files and hidden tests when the experiment was created. |
| `prompt_hash` | sha256 | Hash of the frozen prompt shown to the assistant. |
| `assistant_id` | enum | copilot \| cursor \| claude_code \| codex. |
| `assistant_version` | string|null | Assistant/CLI version if detected or reported by the operator; null when unknown (never guessed). |
| `assistant_version_source` | enum | detected (CLI --version) \| operator (typed by researcher) \| unknown. |
| `model` | string|null | Underlying model as reported by the operator, when known. |
| `attempt_number` | int | Attempt index within the task × assistant pair (1..attempts). |
| `execution_mode` | enum | human (operator-driven) or automated (headless CLI adapter). |
| `eval_mode` | enum | docker (sandboxed) or local (host subprocess) evaluation. |
| `operator` | string | Researcher who executed the run (ACB_OPERATOR). |
| `machine_id` | string | Machine on which the run was executed (ACB_MACHINE_ID). |
| `status` | enum | planned \| ready \| running \| awaiting_human \| submitted \| evaluating \| completed \| failed \| invalidated. |
| `failure_class` | enum|null | task_failure \| timeout \| evaluator_error \| adapter_error \| environment_error \| operator_abort. Null for successful runs. |
| `outcome` | string|null | Evaluator outcome (passed, acceptance_failed, regression_failed, test_timeout, collection_error) or time_limit_exceeded. |
| `success` | bool|null | Run-level functional success = evaluator success AND within the time limit. Null when the run never completed evaluation. |
| `evaluation_success` | bool|null | Raw evaluator verdict, ignoring the time limit. |
| `eligible_for_success` | bool | Effective run with status completed. Only eligible runs form the success-rate denominator. |
| `timed_out` | bool | Wall-clock duration exceeded the time limit (counted as a functional failure). |
| `prepared_at` | iso8601|null | Workspace creation time. |
| `started_at` | iso8601|null | Start of the assistant session. |
| `ended_at` | iso8601|null | End of the assistant session. |
| `submitted_at` | iso8601|null | Submission time. |
| `completed_at` | iso8601|null | Evaluation completion time. |
| `wall_clock_seconds` | float|null | ended_at − started_at in seconds (assistant session duration, excludes evaluation). |
| `time_limit_seconds` | int | Time budget for the attempt. |
| `iterations` | int|null | Number of prompts sent to the assistant (initial prompt = 1). See protocol for the exact definition. |
| `human_interventions` | int|null | Number of human actions beyond prompting (manual edits, approvals, corrective hints). See protocol. |
| `acceptance_passed` | int|null | Hidden acceptance tests (or quality checks) passed. |
| `acceptance_failed` | int|null | Acceptance tests failed. |
| `acceptance_errors` | int|null | Acceptance tests that errored. |
| `acceptance_total` | int|null | Acceptance tests collected. |
| `acceptance_expected` | int|null | Acceptance tests expected from task validation (missing tests count as not passed). |
| `regression_failed` | int|null | Hidden regression tests failed. |
| `regression_errors` | int|null | Hidden regression tests errored. |
| `regression_total` | int|null | Hidden regression tests collected. |
| `regression_failure` | bool|null | At least one regression test failed or errored. |
| `line_coverage` | float|null | Test-writing tasks: line coverage of the target module by the submitted tests (0–1). |
| `mutation_score` | float|null | Test-writing tasks: fraction of hidden mutants detected (0–1). |
| `ruff_status` | enum|null | ran \| unavailable \| error. Unavailable is never treated as zero findings. |
| `ruff_count` | int|null | Ruff findings in the submitted workspace. |
| `ruff_new` | int|null | Ruff findings not present in the starter baseline. |
| `semgrep_status` | enum|null | ran \| unavailable \| error. |
| `semgrep_count` | int|null | Semgrep findings in the submitted workspace. |
| `semgrep_new` | int|null | Semgrep findings introduced relative to the starter baseline. |
| `semgrep_resolved` | int|null | Baseline Semgrep findings no longer present. |
| `files_changed` | int|null | Files added, modified or deleted relative to the starter. |
| `lines_added` | int|null | Added lines in the submission diff. |
| `lines_removed` | int|null | Removed lines in the submission diff. |
| `out_of_scope_count` | int|null | Changed files outside the task scope (allowed_paths). |
| `evaluation_id` | uuid|null | Latest evaluation of the run. |
| `evaluator_version` | string|null | Evaluator version that produced the result. |
| `evaluation_duration_seconds` | float|null | Evaluator runtime. |
| `submission_hash` | sha256|null | Hash of the evaluated workspace snapshot. |
| `failure_modes` | string | Semicolon-separated failure-mode labels assigned by researchers. |
| `invalidation_reason` | string|null | Why the run was invalidated (protocol violation etc.). |
| `notes` | string | Operator notes. |
