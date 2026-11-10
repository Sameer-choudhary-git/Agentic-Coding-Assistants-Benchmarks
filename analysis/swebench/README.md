# SWE-bench Verified re-analysis (Section V-A, this study's own analysis)

Reads the per-instance results of every SWE-bench Verified leaderboard submission from the official
[SWE-bench/experiments](https://github.com/SWE-bench/experiments) repository. It is free, calls no AI
service, and needs only GitHub.

`data/verified_snapshot.json` is a compact snapshot (122 submissions on all 500 instances, repository commit
40f164d5b8, 3 Sep 2026), so the analysis runs offline:

```
python analysis/swebench/verified_analysis.py analyze      # writes analysis/swebench/output/
python paper/build_tables.py                                # copies table, figure and numbers into the paper
```

To refresh the snapshot from the latest leaderboard:

```
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/SWE-bench/experiments swex
git -C swex sparse-checkout set --no-cone "/evaluation/verified/*/metadata.yaml" "/evaluation/verified/*/results/*.json"
python analysis/swebench/verified_analysis.py snapshot --experiments swex
```

Outputs: `summary.json` (trajectory, difficulty bands, per-repository and per-year rates, scaffold spread,
product search, pilot candidates), `instance_hardness.csv`, `swebench_table.tex` and `swebench_verified.{pdf,png}`.

Findings at this snapshot:

- The state of the art rose from 32.6% (June 2024) to 79.2% (December 2025); the median submission resolves 57.0%.
- 29 instances were never solved, and 95 are solved by 90% or more of submissions.
- The same model (Claude 3.5 Sonnet, Oct 2024) scores 33.6–63.4% under 16 different agents.
- Among all 182 Verified entries, none is Copilot, Cursor, Claude Code or the Codex product. The only Codex
  entries are OpenAI models in the generic mini-SWE-agent scaffold.

The pilot sample in `swebench_pilot/candidates.json` is drawn from these difficulty tertiles.
