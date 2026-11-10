# Experimental protocol

Version 1.0. Freeze this document (and record its commit) before the first official run. Any change
afterwards must be dated, justified and applied to all assistants; runs executed under an older
version are analysed separately or invalidated.

## 1. Design

| Factor | Value |
|---|---|
| Assistants | GitHub Copilot, Cursor, Claude Code, OpenAI Codex |
| Tasks | 18 synthetic Python tasks, 3 per category (bug fixing, feature implementation, security remediation, refactoring, test writing, repository reasoning) |
| Attempts | 2 independent attempts per task × assistant |
| Planned attempts | 18 × 4 × 2 = **144** |
| Order | Randomised with a recorded seed (set when the experiment is created) |
| Primary outcome | Functional success (see `metrics-and-data-dictionary.md`) |
| Secondary outcomes | Duration, iterations, human interventions, regressions, Ruff and Semgrep findings, out-of-scope changes, failure modes |

Create the official experiment once, with all 18 tasks, all four assistants and 2 attempts, in the
**docker** evaluation mode. Do not create additional official experiments for the same design;
pilot runs go in a separate experiment named "Pilot …" and are excluded from the analysis.

## 2. Fixed conditions

Keep these identical for every attempt and record deviations in the run notes:

* **Prompt.** Paste the frozen prompt exactly as shown (use *Copy frozen prompt*). Do not add
  context, file hints, the task title or the acceptance-test list. The prompt hash is stored with
  the run.
* **Workspace.** Always a fresh workspace created by the platform (*Create workspace*). Never reuse a
  workspace or open the repository itself in the assistant: hidden tests and reference solutions
  live in the repository. Open exactly the workspace folder (not its parent).
* **Fresh session.** Start a new chat/session for every attempt. Clear project memories, rules files
  and custom instructions that are not part of the default configuration, and do not let an
  assistant see previous attempts.
* **Configuration.** Use the default model and settings of each product's plan, recorded on the
  Assistants page. If you must change a model or mode, do it before the first official run and
  for all attempts of that assistant.
* **Permissions.** Allow the assistant to read and edit files in the workspace and to run `python`
  and `pytest`. Approving a permission prompt is counted as an intervention (see §4); if a product
  allows a "trust this folder / auto-approve edits" setting, enable it once per workspace and note it.
* **Time limit.** Each task has a time limit (20–40 minutes, shown on the run page). Start the timer
  right before pasting the prompt and stop it when the assistant reports it is finished, when you
  give up, or at the limit. A session over the limit counts as not passed.
* **Network.** Assistants need their own network access; the evaluator does not (Docker mode runs
  tests with networking disabled).
* **Operator.** The operator acts as a cooperative but minimal user: no domain hints, no code edits.

## 3. Task readiness

Before the official experiment:

1. Run `npm run validate:tasks` (or `python -m evaluator.cli validate --mode docker`). Every task must
   be *validated*: the starter fails at least one acceptance check, the reference solution passes all
   acceptance and regression tests, the reference stays within scope, and every mutant of a
   test-writing task is detectable.
2. Commit the files in `benchmark_tasks/_validation/`. A later change to a task makes its validation
   *stale* and the platform refuses to include it in new experiments unless explicitly allowed.
3. Prompt review: a team member who did not write the task reads the prompt only (no tests) and
   writes down what they would implement. Discrepancies with the acceptance tests are fixed in the
   prompt and the task version is bumped (`version` in `task.json`). Record reviewer and date in
   `docs/task-review-log.md`.

## 4. What counts as an iteration and an intervention

Apply the same definitions to all four assistants.

**Iteration** — one prompt sent to the assistant. The initial frozen prompt is iteration 1.
Each further message is another iteration, including:

* "continue", "please finish", "you stopped half-way";
* "run the tests again" or "the tests still fail" **without** new information beyond what the
  assistant could see itself.

**Human intervention** — any human action other than sending a prompt, including:

* approving a permission request (file edit, command execution) one at a time;
* editing code, files or configuration by hand;
* giving information not present in the frozen prompt or the workspace (e.g. "look at
  `pricing.py`", "the bug is in the rounding");
* restarting the assistant, reloading the editor, re-indexing, switching model or mode;
* resolving an environment problem for the assistant (installing a package, fixing a path).

Log each one with *Log follow-up prompt* / *Log intervention* while the session runs (add a short
note). The submission form lets you correct the final counts; use it only to fix logging mistakes.

Not counted: reading the assistant's output, scrolling, waiting, copying the prompt, stopping the
timer, submitting.

## 5. Procedure for one attempt (human-operated)

1. Open the experiment and click *Open next run in order* (follows the randomised sequence).
2. *Create workspace.* Copy the workspace path.
3. Open the folder in the assistant (VS Code for Copilot, Cursor for Cursor, a terminal for Claude
   Code and Codex). Confirm the assistant version on the run page (leave empty if unknown).
4. Click *Start session timer*, then paste the frozen prompt into a new session.
5. Let the assistant work. Log follow-up prompts and interventions as they happen.
6. When the assistant is done (or the time limit is reached), click *Stop timer*. Do not edit files
   afterwards.
7. Submit with *Use the files in the workspace folder* (or paste a patch if the assistant produced a
   diff elsewhere), confirm the counts and add notes. Evaluation starts automatically.
8. Review the result. Add failure-mode labels later, during the blinded review (§7).

If something breaks that is not the assistant's fault (machine crash, outage, wrong workspace),
use *Mark operational failure* with a description, then *Retry attempt*. If the protocol was
violated (wrong prompt, opened the repository instead of the workspace), *Invalidate run* with the
reason and retry. Both actions keep the original record.

## 6. Automated mode (optional)

A headless CLI adapter may be used only for an assistant whose integration status is *Supported*
after manual verification (see `assistant-integrations.md`). Do not mix human-operated and
automated runs for the same assistant within the official experiment: interaction styles differ and
iterations/interventions are not comparable. Report the execution mode for each assistant.

## 7. Blinded review and failure taxonomy

After all runs are complete, two team members independently review each non-passing run's patch
(`submission.patch`), test output and logs with the assistant name hidden (use the run ID only;
the JSONL export can be filtered to remove `assistant_id`). Each reviewer assigns failure modes from
the fixed taxonomy (misunderstood requirements, repository context error, incomplete implementation,
dependency issue, repeated failed attempts, regression introduced, security weakness, changed files
outside scope, other). Disagreements are discussed and the agreed labels are saved on the run page.
Record raw agreement before discussion.

## 8. Exclusion criteria (decided before data collection)

* Invalidated runs and operational failures are excluded from success rates and reported as missing
  data. Each must be retried until a completed run exists, or the attempt is reported as missing.
* Runs evaluated in a different evaluation mode from the experiment's mode are not allowed (the mode
  is fixed per experiment).
* Pilot experiments are excluded.

## 9. Data management

* Each team member works in their own clone with their own `data/acb.sqlite` and `ACB_OPERATOR`.
* To avoid duplicate work, divide the official experiment by assistant: one member creates the
  official experiment and shares the *bundle* export; the others import it, then each member only
  executes runs for their assigned assistants and exports a bundle at the end of each session.
  Imports are idempotent and never overwrite conflicting records.
* Back up `data/` and `artifacts/` after every session.
