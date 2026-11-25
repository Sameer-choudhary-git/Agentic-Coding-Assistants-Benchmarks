# Codex on the Golden core-12 pilot

**Experiment:** `Codex core-12` (`18cbed12-083d-4b5b-b1f4-aa629f84c3fe`), run on 2026-11-25 on laptop 1 (WINTER).
**Status:** all 12 runs completed and scored. This is a **pilot**: one agent, 12 tasks, one attempt each. It is not
yet a comparison between agents.

## 1. Setup

| Item | Value |
|---|---|
| Agent | OpenAI Codex CLI 0.172.0, headless (`codex exec`) |
| Model | `gpt-6-luna`, reasoning effort `medium` (from the Codex run log; the app's `model` field was left empty) |
| Sandbox | `workspace-write`: edits only inside the task workspace, no network, so no web search and no look-up of the upstream fix |
| Interaction | Frozen app prompt, given once. No follow-up prompts and no human help (iterations = 1, interventions = 0 by design) |
| Attempts / time limit | 1 attempt per task, 30-minute limit |
| Tasks | 12 tasks from the reviewed balanced core, 2 per domain (`docs/codex-runs-for-teammate.md`) |
| Correctness scoring | Hidden tests in Docker: official SWE-bench harness (Verified, Multilingual, Multimodal) or SWE-bench Pro's image and scripts. Resolved = every FAIL_TO_PASS and every PASS_TO_PASS test passes. |
| Quality scoring | Golden Code Quality Module on the patch only (0–100), compared with the real upstream fix |
| Run order | Randomised by the app; runs were started one at a time with `scripts/batch_run.py --max-runs 1` |

## 2. Headline results

| Metric | Codex |
|---|---|
| **Resolved** | **6 / 12 = 50.0%** (Wilson 95% CI 25.4% – 74.6%) |
| **Domain-balanced success** | **50.0%** (bootstrap 95% CI 33.3% – 66.7%) |
| Runs that broke existing tests | 2 / 12 (element-web-27139ca68e, p5-js-3709) |
| Mean QualityScore, all scored patches | 98.6 (n = 11; one run produced no patch) |
| Mean QualityScore, resolved patches | 97.4 (n = 6) |
| Difference from the reference fix | −0.3 points on average |
| Agent time per task | median 40 s (range 18 – 76 s); 8.4 minutes in total |
| Tests added by the agent | none (expected: the prompt says not to modify tests) |

### By domain (resolved / completed)

| Bug fix | Feature | Frontend/visual | Performance | Refactoring | Security fix |
|---|---|---|---|---|---|
| 2/2 | 0/2 | 0/2 | 2/2 | 1/2 | 1/2 |

### By source and difficulty (exploratory)

| SWE-bench Pro | Verified | Multilingual | Multimodal |
|---|---|---|---|
| 4/5 | 1/2 | 1/3 | 0/2 |

| Easy | Medium | Hard |
|---|---|---|
| 5/9 | 0/2 | 1/1 |

## 3. Per-task results

| Task | Domain | Tier | Source | Outcome | FAIL_TO_PASS | PASS_TO_PASS failed | Patch (+/−) | Quality | Reference | Agent time |
|---|---|---|---|---|---|---|---|---|---|---|
| element-hq__element-web-ce554276db | Bug fix | easy | Pro | ✅ passed | 6/6 | 0/107 | +24/−3 | 100 | 100 | 45 s |
| faker-ruby__faker-2970 | Bug fix | easy | Multilingual | ✅ passed | 1/1 | 0/8 | +5/−1 | 96 | 100 | 30 s |
| sphinx-doc__sphinx-8035 | Feature | medium | Verified | ❌ acceptance failed | 0/1 | 0/2 | +21/−2 | 100 | 97 | 40 s |
| tokio-rs__tokio-6724 | Feature | easy | Multilingual | ❌ does not compile | — | — | +11/−2 | 100 | 100 | 41 s |
| diegomura__react-pdf-1280 | Frontend | easy | Multimodal | ❌ acceptance failed | 0/1 | 0/210 | +4/−1 | 100 | 100 | 39 s |
| processing__p5-js-3709 | Frontend | easy | Multimodal | ❌ acceptance + regression failed | 10/12 | 19/1535 | +17/−2 | 100 | 100 | 53 s |
| django__django-16801 | Performance | easy | Verified | ✅ passed | 1/1 | 0/17 | +2/−1 | 100 | 100 | 27 s |
| NodeBB__NodeBB-767973717b | Performance | hard | Pro | ✅ passed | 7/7 | 0/268 | +95/−0 | 98.2 | 94 | 76 s |
| qutebrowser__qutebrowser-44e64199ed | Refactoring | easy | Pro | ✅ passed | 3/3 | 0/51 | +22/−10 | 96 | 96 | 31 s |
| element-hq__element-web-27139ca68e | Refactoring | medium | Pro | ❌ regression failed | 3/3 | 4/149 | +27/−9 | 100 | 100 | 40 s |
| caddyserver__caddy-6115 | Security fix | easy | Multilingual | ❌ empty patch | — | — | 0/0 | — | 97 | 18 s |
| NodeBB__NodeBB-97c8569a79 | Security fix | easy | Pro | ✅ passed | 1/1 | 0/197 | +18/−1 | 94 | 100 | 63 s |

## 4. What went wrong in the 6 failures

| Task | What happened |
|---|---|
| caddy-6115 | Codex's final message said it had updated `selectionpolicies.go`, but its log shows no edit and the workspace was unchanged. The claimed fix was never made. The same happened in the earlier test run of this task. |
| tokio-6724 | The patch applied cleanly but the crate no longer compiles (Rust borrow error `E0502` in `write_all_buf.rs`). SWE-bench reports this as "patch not applied" because no test could run. It is a compile failure by the agent. |
| element-web-27139ca68e | The new behaviour works (FAIL_TO_PASS 3/3), but 4 existing tests broke. |
| p5-js-3709 | 10 of 12 target tests pass and 19 of 1535 existing tests fail. Partly correct, with regressions. |
| sphinx-8035, react-pdf-1280 | Patches were made but the target test still fails. |

**A shared pattern: Codex did not verify its work.** It finished every task in under 80 seconds. In 11 of 12 logs
there is no build or test command; only faker-2970 shows one. Nine final messages say it "did not run" the tests,
and two say it "did not run tests, **as requested**". Codex read the prompt's *"Do not modify or add tests unless
the issue explicitly asks for it; hidden tests will be run afterwards"* as an instruction not to run tests. At
least two failures (tokio's compile error, element-web-27139ca68e's broken tests) would have shown up in a build or
test run.

This matters for the comparison (see section 7). The prompt is identical for every agent, so the comparison stays
fair, but it may discourage testing more for some agents than others.

## 5. Code quality

Codex's patches are small and clean. 7 of 11 patches score 100, and the average equals the reference fixes'
(−0.3).

| Task | Score | What cost points |
|---|---|---|
| NodeBB-97c8569a79 | 94 | complexity: a function's cyclomatic complexity grew noticeably |
| qutebrowser-44e64199ed | 96 | hygiene: 1 lint-suppression comment added |
| faker-2970 | 96 | size: the patch is 3.0× the size of the reference fix |
| NodeBB-767973717b | 98.2 | complexity grew slightly; 1 line over 120 characters |

Mean sub-scores (0–100):

| Reliability | Complexity | Maintainability | Security | Hygiene | Size |
|---|---|---|---|---|---|
| 100 | 97 | 100 | 100 | 96 | 93 |

There were no new lint errors and no new security findings. Patches were usually smaller than the reference fix
(median 0.8× its size).

## 6. Validity notes

- **Scoring is checked.** On this machine the smoke test resolved the reference fixes of caddy-6115 (Multilingual)
  and NodeBB-97c8569a79 (Pro) and rejected do-nothing patches. Earlier checks also covered one task each from
  Verified and Multimodal.
- **Infrastructure errors were fixed without rerunning the agent.**
  - The first scoring of react-pdf-1280 and django-16801 failed because Docker was not reachable.
  - Three SWE-bench Pro tasks (NodeBB-767973717b, qutebrowser-44e64199ed, element-web-ce554276db) failed
    because Docker could not download their images (a WSL credential-helper error).
  - After each fix, Codex's **saved patch** was re-scored. No agent run was repeated, and all 12 results come
    from Codex's first and only attempt.
- **Excluded runs:** the experiments "Codex test" (failed: wrong model name), "Codex test 2" and "test" were
  setup checks and are not part of these results.
- **Mode:** headless only. Iterations and interventions are fixed by design and are not results.

## 7. Limitations

- **Small sample.** With 12 tasks and 1 attempt, the 95% interval for success is 25–75%. Per-domain rates rest on
  2 tasks each, so read them as anecdotal.
- **One agent.** No comparison is possible until the Claude Code runs on the same 12 tasks (laptop 2) are
  imported. The pairwise table is empty for that reason.
- **Model not stored by the app.** The `model` column in the export is empty; `gpt-6-luna` / `medium` comes from
  Codex's own log. Record it in the experiment notes.
- **p5-js-3709 regressions** (19 of 1535 tests) were not cross-checked against the reference fix in this
  environment. Some could be environment flakiness. Running `golden/scripts/smoke_harness.py` on this task would
  settle it.
- **Outcome label.** The app labels tokio's compile failure `patch_failed`. Report it as a compile failure.
- **Prompt wording and testing.** Codex treated "do not modify or add tests" as "do not run tests". Keep the prompt
  unchanged for every agent in this study, so all agents get the same prompt, and report this effect. If the
  prompt is reworded (for example, "you may run the existing tests"), every agent must be rerun with the new
  wording.
- **Excluded experiments.** "Codex test", "Codex test 2" and "test" in the same database are setup checks; never
  export them with the study.

## 8. Next steps

1. Run Claude Code on the same 12 tasks (laptop 2), then import this experiment's **Team exchange bundle** there.
2. Rebuild the score table with both agents. The pairwise McNemar and quality comparison will fill in:
   `python golden/scripts/score_table.py --input <results csv(s)>`.
3. For the paper, extend to the full 30-task core and, if the budget allows, 2–3 attempts per task.

## Data

- Results export: `artifacts/exports/codex-core12/results.csv` (local, not in git)
- Score table: `artifacts/exports/codex-core12/score_table/score_table.md`
- Per-run artifacts (agent log, patch, test logs, quality report): `artifacts/runs/<run id>/`
