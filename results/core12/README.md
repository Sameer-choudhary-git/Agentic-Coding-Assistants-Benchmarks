# Golden core-12 results (shared data)

Raw and processed results of the 12-task Golden core pilot, so every team member has the same data. The runs
were made on laptop 1 (WINTER) on 2026-11-25. See [REPORT.md](REPORT.md) for the analysis.

| Assistant | Experiment | Resolved | Notes |
|---|---|---|---|
| OpenAI Codex CLI 0.172.0 (`gpt-6-luna`, medium) | `18cbed12-083d-4b5b-b1f4-aa629f84c3fe` | 6/12 | headless, network sandbox |
| GitHub Copilot CLI 1.0.115 (`auto` / Copilot Fusion) | `56546823-6159-4b03-92d1-ec245f124c05` | 7/12 | headless, `web_fetch` removed, network shell commands denied |
| Claude Code | laptop 2 | — | add its bundle here when done |
| Cursor | — | — | not run yet |

## Contents

| Path | What |
|---|---|
| `REPORT.md` | The comparison report (copy of `docs/reports/core12-final-report.md`) |
| `bundles/<agent>-core12.bundle.json` | **Team exchange bundles**: the full experiment records (runs, evaluations, test outcomes, events) with a checksum. Import these into your own app to get identical data. |
| `csv/<agent>-core12-results.csv` | One row per run (outcome, tests, quality, time…); `csv/data-dictionary.md` defines every column |
| `csv/<agent>-core12-summary.csv` | Aggregates with Wilson intervals |
| `csv/<agent>-core12-config.json` | Frozen experiment configuration (tasks, prompt hashes, planned matrix) |
| `score_table/` | Paper tables built from both CSVs (`score_table.md` + one CSV per table) |
| `runs/<agent>/<task id>/` | Evidence for each run, described below |

Each `runs/<agent>/<task id>/` folder holds:

| File | What |
|---|---|
| `prompt.md` | the exact frozen prompt the agent received |
| `agent_stdout.txt`, `agent_stderr.txt` | the agent's full transcript and final message |
| `patch.diff` | the agent's submitted change |
| `scoring_report.json` | the evaluator's report: outcome, FAIL_TO_PASS / PASS_TO_PASS results, code-quality score and findings |
| `harness_*` / `pro_*` | the SWE-bench (or SWE-bench Pro) harness output. Test logs are gzipped; open them with `zcat` or 7-Zip. |

Only the final scoring of each run is included. Runs whose first scoring failed because of Docker were re-scored
from the same saved patch; the agent never ran twice.

## Use the data

**Import into your app** (Ubuntu, app running) so it appears on the Results page:
```bash
npm run import-bundle --workspace backend -- results/core12/bundles/codex-core12.bundle.json
npm run import-bundle --workspace backend -- results/core12/bundles/copilot-core12.bundle.json
```
Or use Exports → Import in the app. Identical records are skipped and nothing is overwritten.

**Rebuild the score table**, adding more assistants' CSVs when they exist:
```bash
python3 golden/scripts/score_table.py --input results/core12/csv/codex-core12-results.csv results/core12/csv/copilot-core12-results.csv --out results/core12/score_table
```

**Adding a new assistant** (e.g. Claude Code from laptop 2):
1. Export its bundle and `results` CSV from the app.
2. Put them in `bundles/` and `csv/` with the same naming.
3. Rebuild the score table and update `REPORT.md`.

Never run the same (task, assistant, attempt) on two laptops.
