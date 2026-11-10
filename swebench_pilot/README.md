# SWE-bench Verified pilot (human-operated)

**Recommended: run it inside the app.** After `select` has downloaded the dataset, the 12 tasks appear on the
Tasks page under "SWE-bench Verified". Create an experiment with that benchmark (12 × 4 × 1 = 48 runs) and
work each run as usual. The app clones the repository, times the session, logs prompts and interventions, and
scores the patch with the official harness. The command-line steps below do the same thing without the app.

A small, seeded sample of real SWE-bench Verified issues, worked by an operator with each of the four
assistants under the platform's protocol, then scored with the official SWE-bench harness. It turns
published model-level scores into product-level evidence for Section V-A.

Nothing here calls an AI API. The assistants are used through their normal apps by the operator, under
your own subscriptions. Downloading the dataset and running the harness are free but need Docker and
disk space.

```
pip install swebench datasets
python swebench_pilot/pilot.py select   --n 12 --seed 2026            # writes manifest.json (IDs come from the dataset)
python swebench_pilot/pilot.py prepare  --manifest swebench_pilot/manifest.json --assistant cursor --workspaces ~/acb-swe
#   work each folder with the assistant; follow docs/experimental-protocol.md; leave changes uncommitted
python swebench_pilot/pilot.py collect  --manifest swebench_pilot/manifest.json --assistant cursor --workspaces ~/acb-swe --out swebench_pilot/preds/cursor.jsonl
python swebench_pilot/pilot.py evaluate --predictions swebench_pilot/preds/cursor.jsonl --run-id pilot1
python swebench_pilot/pilot.py summarize --reports-dir . --out swebench_pilot/results.csv
python paper/build_tables.py                                           # puts the pilot table into the paper
```

Design notes:

- **Selection.** `select` is stratified by Verified's difficulty labels and spread across repositories. The
  manifest stores a hash of each problem statement and refuses to load if one is edited.
- **Counterbalancing.** Use the same manifest for every assistant and rotate which assistant goes first per
  instance, to limit learning effects. With 12 instances × 4 assistants = 48 sessions, results are a pilot
  and must be reported with exact counts, not percentages alone.
- **Scoring.** `collect` diffs each workspace against the base commit, excluding `PILOT_TASK.md`. A missing
  workspace becomes an empty patch, which still counts as submitted and unresolved.
