# Status against the IEEE paper outline (updated 9 Nov 2026)

| # | Outline section | Work item | Status | Where |
|---|---|---|---|---|
| 1 | I, III, V | Reference verification | Done: 23 sources checked; 3 outline corrections recorded | `evidence/sources.json`, `paper/literature-summary.md` |
| 2 | V | Evidence registry, Evidence page, CSV/LaTeX export | Done: 47 sourced figures | `evidence/evidence.json`, UI "Literature evidence", `GET /api/v1/evidence[/export]` |
| 3 | V | AIDev dataset analysis | Script done and tested on synthetic data; **run on your PC** (Hugging Face blocked here) | `analysis/aidev/` |
| 4 | IV | Feature comparison table | Done (vendor docs, checked 9 Nov 2026) | `evidence/assistant_features.json`, `paper/tables/features.tex` |
| 5 | II, IV | Background and comparison text | Done | `paper/main.tex` |
| 6a | V-A | SWE-bench Verified re-analysis (real leaderboard data) | Done: 122 submissions, table + figure in paper | `analysis/swebench/` |
| 6 | III, V | Own experiment | Integrated into the app as a second benchmark (Tasks, Experiments, runs, Dashboard and Results); 12-instance sample in `candidates.json`; **runs pending** (needs the four assistants, Docker, and Hugging Face access) | `swebench_pilot/` |
| 7 | VI | Risks | Done | `paper/main.tex` |
| 8 | all | IEEE LaTeX paper | Done: 5 pages, compiles | `paper/` |
| 9 | I | Contribution statement vs arXiv:2602.08915 | Done | `paper/main.tex`, Section I |

## Still to do (needs you)

1. Add author names and affiliations in `paper/main.tex`.
2. Run the AIDev re-analysis and, if wanted, add `\input{tables/aidev.tex}` to Section V-C.
3. Run the SWE-bench pilot with real assistants, then `python paper/build_tables.py` and recompile.
4. Re-check product facts in Table I just before submission.
5. Optional: run the original 18-task, 144-attempt platform experiment as extra primary evidence.
