# AIDev re-analysis (Sections V-B and V-C)

Recomputes PR acceptance (merged/closed) by agent and task type from the public AIDev dataset, following
Pinna et al. (arXiv:2602.08915): Wilson 95% intervals, chi-square tests of agent differences within each
task type (cells with n ≥ 10), Holm correction.

```
pip install pandas pyarrow scipy matplotlib huggingface_hub
python analysis/aidev/aidev_analysis.py download --data-dir data/aidev
python analysis/aidev/aidev_analysis.py analyze  --data-dir data/aidev --out analysis/aidev/output
```

Outputs: `acceptance_by_agent.csv`, `acceptance_by_type.csv`, `acceptance_by_agent_type.csv`,
`chi_square_by_type.csv`, `aidev_table.tex`, `aidev_heatmap.png` and `summary.json`.

The default tables are the curated subset (`pull_request.parquet`, `pr_task_type.parquet`). If the dataset
renames a table or column, pass `--pr-table` / `--type-table` or edit `COLUMN_ALIASES`; the script names the
missing column. It was tested on synthetic data only, because Hugging Face is not reachable from the build
environment.
