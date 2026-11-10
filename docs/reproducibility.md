# Reproducibility

## What is frozen and recorded

| Item | Where |
|---|---|
| Task content (metadata, prompt, starter, hidden tests) | SHA-256 `task_hash` per task, frozen per planned attempt when an experiment is created; checked again by the evaluator at every evaluation |
| Prompt | `prompt_hash`; the exact prompt text of every task version is kept in `task_versions` |
| Hidden tests | `test_hash` and `test_version` |
| Task validation | `benchmark_tasks/_validation/<ID>.json` with the hash it applies to, evaluator version and mode |
| Run order | experiment `seed` (deterministic shuffle) |
| Assistant | version (detected / operator-reported / unknown), model, execution mode |
| Environment | evaluator version, host Python, container Python and pytest versions, Docker server version, Ruff and Semgrep versions — in every `report.json` and in the export manifest |
| Evaluation configuration | `evaluator/config/ruff.toml`, `evaluator/config/semgrep/rules.yml`, `docker/evaluator.Dockerfile` (pytest version pinned) |
| Submission | workspace snapshot hash and `submission.patch` |
| History | `events` table: every transition with actor and timestamp |

Hashes normalise CRLF line endings, so Windows and Linux checkouts of the same task hash identically.

## Re-running an evaluation

Every run keeps its workspace (`ACB_WORKSPACE_ROOT`) and patch. To reproduce a verdict:

```bash
python -m evaluator.cli evaluate --task BF-01 --workspace <workspace path> --out /tmp/re-eval \
  --mode docker --expected-task-hash <task_hash from the run>
```

Or apply `artifacts/runs/<run-id>/evaluations/<id>/submission.patch` to a fresh workspace created
with `create-workspace` and evaluate that.

## Reproducing the analysis

```bash
npm run export -- <experiment-id>          # writes artifacts/exports/<timestamp>-<id>/
python analysis/analyze.py --input artifacts/exports/<timestamp>-<id>/results-<id>.csv --out analysis/output
```

`CHECKSUMS.json` in the export folder lists the SHA-256 of every exported file; quote these hashes in
the report so readers can verify the dataset.

## Things that cannot be frozen

* Commercial assistants change models and behaviour without notice. Record versions on every run,
  run the whole study within a short window, and interleave assistants (randomised order) so that a
  mid-study change affects all assistants similarly in time.
* Human operators differ. Use the protocol's definitions, and record the operator per run.
* LLM outputs are stochastic; two attempts per pair give a first indication of variability only.
