# Golden core-12: Codex vs GitHub Copilot

**Date:** 2026-11-25. **Machine:** laptop 1 (WINTER), app run from WSL Ubuntu, Docker scoring.
**Experiments:** `Codex core-12` (`18cbed12-…`) and `Copilot core-12` (`56546823-…`). All 24 runs are completed
and scored.
**Status:** two of the four planned assistants. Claude Code is being run on laptop 2 and Cursor is not started.
Add both to this report once their bundles are imported. This is a 12-task pilot with one attempt per task, so
read the differences as indicative, not conclusive.

## 1. Setup (identical for both assistants)

| Item | Codex | GitHub Copilot |
|---|---|---|
| Tool | OpenAI Codex CLI 0.172.0, `codex exec` | GitHub Copilot CLI 1.0.115, `copilot -p` |
| Model | `gpt-6-luna`, reasoning effort medium (pinned) | `auto` = Copilot Fusion, the only model on the plan used; Copilot picks the underlying model and does not log it |
| Mode | headless, non-interactive | headless, non-interactive |
| Web access | none: `workspace-write` sandbox blocks the network | `web_fetch` tool removed (`--excluded-tools`); `curl`, `wget`, `gh`, `git fetch/pull/clone` denied; GitHub MCP tools disabled |
| Interaction | frozen prompt once; iterations = 1, interventions = 0 by design | same |
| Tasks / attempts / limit | 12 core tasks (2 per domain), 1 attempt, 30 min | same |
| Scoring | hidden FAIL_TO_PASS + PASS_TO_PASS tests in Docker; Golden Code Quality Module on the patch | same |

**Web-access check:** all 12 Copilot logs show `Disabled tools: web_fetch`, no blocked command attempts, and no
fetched pages. The only URLs in the logs come from file contents (a license header and a yarn message). Codex's
sandbox has no network.

## 2. Headline results

| Metric | Codex | Copilot |
|---|---|---|
| **Resolved** | 6/12 = **50.0%** [25.4–74.6%] | 7/12 = **58.3%** [32.0–80.7%] |
| **Domain-balanced success** | **50.0%** [33.3–66.7%] | **58.3%** [41.7–75.0%] |
| Runs that broke existing tests | 2 | 2 |
| Mean QualityScore, all patches | 98.6 (n = 11) | 99.3 (n = 12) |
| Mean QualityScore, resolved patches | 97.4 (n = 6) | 98.8 (n = 7) |
| Difference from the reference fix | −0.3 | +0.6 |
| Agent time per task, median (total) | 40 s (8.4 min) | 52 s (11.8 min) |
| Tried to build or run tests | 1 of 12 runs | 8 of 12 runs |
| Empty patches | 1 | 0 |
| Usage | 237k tokens in total (Codex's own count) | 8.17 AI credits; about 3.0M input tokens, mostly cached |

95% intervals are Wilson for success and a stratified bootstrap for domain-balanced success. The token figures
are each tool's own counter and are not directly comparable.

### Paired comparison (same 12 tasks)

| | Count | Tasks |
|---|---|---|
| Both resolved | 5 | django-16801, NodeBB-767973717b, NodeBB-97c8569a79, element-web-ce554276db, qutebrowser-44e64199ed |
| Only Codex | 1 | faker-2970 |
| Only Copilot | 2 | sphinx-8035, tokio-6724 |
| Neither | 4 | caddy-6115, react-pdf-1280, p5-js-3709, element-web-27139ca68e |

Exact McNemar test: p = 1.00 (1 vs 2 discordant tasks). **The difference in success is not statistically
significant.** The paired quality difference (Codex − Copilot) is −0.7 points [95% CI −1.5, 0.0]: both write very
clean patches.

### By domain (resolved / completed)

| Domain | Codex | Copilot |
|---|---|---|
| Bug fix | 2/2 | 1/2 |
| Feature implementation | 0/2 | **2/2** |
| Frontend/visual | 0/2 | 0/2 |
| Performance | 2/2 | 2/2 |
| Refactoring | 1/2 | 1/2 |
| Security fix | 1/2 | 1/2 |

## 3. Per-task results

| Task | Domain | Tier | Codex | Copilot |
|---|---|---|---|---|
| element-web-ce554276db | Bug fix | easy | ✅ passed | ✅ passed |
| faker-2970 | Bug fix | easy | ✅ passed | ❌ target test fails |
| sphinx-8035 | Feature | medium | ❌ target test fails | ✅ passed |
| tokio-6724 | Feature | easy | ❌ does not compile | ✅ passed |
| react-pdf-1280 | Frontend | easy | ❌ target test fails | ❌ target test fails |
| p5-js-3709 | Frontend | easy | ❌ 10/12 target, 19 regressions | ❌ 10/12 target, 0 regressions |
| django-16801 | Performance | easy | ✅ passed | ✅ passed |
| NodeBB-767973717b | Performance | hard | ✅ passed | ✅ passed |
| qutebrowser-44e64199ed | Refactoring | easy | ✅ passed | ✅ passed |
| element-web-27139ca68e | Refactoring | medium | ❌ 3/3 target, 4 regressions | ❌ 0/3 target, 4 regressions |
| caddy-6115 | Security fix | easy | ❌ empty patch | ❌ target passes, 1 regression |
| NodeBB-97c8569a79 | Security fix | easy | ✅ passed | ✅ passed |

## 4. Observations

1. **Verification behaviour differs most.** Codex ran a build or test command in only 1 of 12 runs and twice
   said it skipped tests "as requested". It read the prompt's "do not modify or add tests" as "do not run tests".
   Copilot tried to build or test in 8 of 12 runs, though often without success: the workspaces have no installed
   dependencies (e.g. "pytest is unavailable"). Copilot's two extra wins (tokio compiles; sphinx) fit this
   pattern.
2. **Code quality is high for both and close to the human reference fixes.** The only findings were one
   lint-suppression comment each on qutebrowser, small complexity increases, and one patch 3× the reference size
   (Codex on faker).
3. **Frontend/visual tasks failed for both** (0/4). These Multimodal tasks come with screenshots of the visual
   problem, which a text-only headless agent never sees. This is a property of the setup, worth stating in the
   paper.
4. **Codex produced one empty patch** (caddy): its final message claimed an edit that it never made.
5. **Copilot is slower and uses more tokens** (median 52 s vs 40 s). Its token count includes large cached
   context.

## 5. Validity notes

- **Same protocol for both:** headless mode, the frozen prompt, one attempt, a 30-minute limit, no web access,
  and the same scorer on the same machine. Runs started one at a time in a randomised order.
- **Scoring checked:** reference fixes resolve and do-nothing patches fail (smoke test on caddy-6115 and
  NodeBB-97c8569a79 on this machine; earlier checks also covered Verified and Multimodal tasks).
- **Infrastructure errors** (Docker unreachable; Pro images that could not be downloaded) were fixed and the
  **saved patches re-scored**. No agent run was repeated: every result is the assistant's first and only attempt.
- **Excluded experiments:** "Codex test", "Codex test 2", "Copilot test" and "test" were setup checks.

## 6. Limitations

- **Small sample:** 12 tasks × 1 attempt. Success intervals are about ±25 points, and per-domain results rest on 2
  tasks. Nothing here is statistically significant.
- **Two of four assistants.** Claude Code (laptop 2) and Cursor are not yet included.
- **Model confound:** Codex used a pinned `gpt-6-luna`. Copilot used `auto` (Copilot Fusion), so its underlying
  model is unknown and may have varied per task. Results compare the tools as shipped with these model settings.
- **Prompt wording:** "do not modify or add tests" suppressed testing for Codex. The prompt was identical for
  both tools, so the comparison is fair, but report the effect.
- **No test environment in the workspace:** agents cannot easily run the project's tests locally (dependencies
  are not installed). This affects every tool equally, and it limits self-verification.
- **Web blocking for Copilot is rule-based** (tool removal plus denied shell commands), not a network sandbox. The
  log scan found no web access.
- **Frontend tasks** include screenshots the agents cannot see.

## 7. Next steps

1. Import the Claude Code core-12 bundle from laptop 2, and run Cursor with the same protocol.
2. Rebuild the tables with all four assistants:
   `python golden/scripts/score_table.py --input <each results.csv> --out analysis/score_table`.
3. For the paper: extend to the full 30-task core and 2–3 attempts per task to get usable confidence intervals.
4. Decide, before scaling up, whether to keep the prompt as is or reword the test instruction (then rerun all
   tools).

## Data

- Exports: `artifacts/exports/codex-core12/results.csv`, `artifacts/exports/copilot-core12/results.csv` (local)
- Combined score table: `artifacts/exports/final-core12/score_table/score_table.md` (local)
- Per-run logs, patches, test logs and quality reports: `artifacts/runs/<run id>/` (local)
- Codex-only report: `docs/reports/codex-core12-report.md`
