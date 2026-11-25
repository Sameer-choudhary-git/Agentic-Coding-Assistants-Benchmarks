| Field | Type | Description |
|---|---|---|
| `experiment_id` | uuid | Experiment identifier. |
| `experiment_name` | string | Human-readable experiment name. |
| `planned_attempt_id` | uuid | One cell of the experiment matrix (task × assistant × attempt number). |
| `run_id` | uuid | One execution of a planned attempt. Retries create new run ids; history is never overwritten. |
| `run_number` | int | 1 for the original run, 2+ for retries of the same planned attempt. |
| `retry_of_run_id` | uuid|null | Run that this run retries (only operational failures or invalidated runs can be retried). |
| `is_effective_run` | bool | True for the latest run of each planned attempt; only effective runs enter aggregate metrics. |
| `task_id` | string | Task identifier, e.g. BF-01 or a SWE-bench instance id such as django__django-16661. |
| `task_category` | enum | bug_fixing \| feature_implementation \| security_remediation \| refactoring \| test_writing \| repository_reasoning \| swebench_verified \| performance \| frontend_visual (golden tasks use their dataset domain). |
| `task_difficulty` | enum | easy \| medium \| hard (criteria in docs/experimental-protocol.md). |
| `task_kind` | enum | standard (hidden acceptance tests), test_writing (coverage + mutation checks) or swebench (official SWE-bench harness). |
| `task_benchmark` | enum | custom (the 18-task suite), swebench_verified (pilot issues) or golden (golden-dataset tasks from SWE-bench Verified, Multilingual, Multimodal and Pro). |
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
| `quality_status` | enum|null | SWE-bench / golden tasks: code quality of the assistant's patch. ran \| unavailable \| error \| not_applicable (empty patch). Unavailable is never treated as a score. |
| `quality_score` | float|null | QualityScore 0–100 of the patch (golden Code Quality Module: 100 minus capped penalties for new lint findings, complexity, maintainability drop, security findings, hygiene and size). Only problems the patch introduces count. |
| `quality_gold_score` | float|null | The reference fix's QualityScore on the same scale (golden tasks). |
| `quality_reliability` | float|null | Sub-score 0–100 (also quality_complexity, quality_maintainability, quality_security, quality_hygiene, quality_size). |
| `quality_complexity` | float|null | Sub-score 0–100: new over-complex functions, complexity growth. |
| `quality_maintainability` | float|null | Sub-score 0–100: maintainability-index drop (Python). |
| `quality_security` | float|null | Sub-score 0–100: new bandit findings and insecure patterns. |
| `quality_hygiene` | float|null | Sub-score 0–100: debug prints, TODOs, commented-out code, suppressions, stray files. |
| `quality_size` | float|null | Sub-score 0–100: patch bloat relative to the reference fix. |
| `evaluation_id` | uuid|null | Latest evaluation of the run. |
| `evaluator_version` | string|null | Evaluator version that produced the result. |
| `evaluation_duration_seconds` | float|null | Evaluator runtime. |
| `submission_hash` | sha256|null | Hash of the evaluated workspace snapshot. |
| `failure_modes` | string | Semicolon-separated failure-mode labels assigned by researchers. |
| `invalidation_reason` | string|null | Why the run was invalidated (protocol violation etc.). |
| `notes` | string | Operator notes. |
