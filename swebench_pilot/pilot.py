"""Hands-on SWE-bench Verified pilot for the four assistants (outline Section V-A, our own data).

Published SWE-bench scores are model-plus-scaffold results; none is reported for the four products as
developers use them. This pilot puts a small, seeded sample of real Verified issues through each
assistant under the same human-operated protocol as the platform, then scores the patches with the
official SWE-bench harness.

Steps (all on your machine; nothing here calls an AI service or costs money):

    pip install swebench datasets           # harness and dataset loader
    python swebench_pilot/pilot.py select   --ids-from swebench_pilot/candidates.json --out swebench_pilot/manifest.json
    python swebench_pilot/pilot.py prepare  --manifest swebench_pilot/manifest.json --assistant claude_code \
                                            --workspaces ~/acb-swe
    #   ... operator works each issue with the assistant in ~/acb-swe/claude_code/<instance_id> ...
    python swebench_pilot/pilot.py collect  --manifest swebench_pilot/manifest.json --assistant claude_code \
                                            --workspaces ~/acb-swe --out swebench_pilot/preds/claude_code.jsonl
    python swebench_pilot/pilot.py evaluate --predictions swebench_pilot/preds/claude_code.jsonl --run-id pilot1
    python swebench_pilot/pilot.py summarize --reports-dir . --out swebench_pilot/results.csv

The harness builds Docker images (roughly 100 GB of disk for many instances; a dozen is far less).
Instance IDs are never written by hand: ``select`` draws them from the dataset with a fixed seed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

DATASET = "princeton-nlp/SWE-bench_Verified"
ASSISTANTS = ["copilot", "cursor", "claude_code", "codex"]

TASK_TEMPLATE = """# SWE-bench Verified pilot: {instance_id}

Repository: {repo} at commit {base_commit}

Resolve the issue below by editing the code in this folder. Do not edit or add tests unless the issue
asks for it; hidden tests will be run afterwards. When you are done, leave the changes uncommitted.

Protocol reminders for the operator: use the standard prompt from docs/experimental-protocol.md,
log every follow-up prompt and intervention, and stop at the time limit ({time_limit} minutes).

---

{problem_statement}
"""


def load_dataset_rows(split: str = "test") -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError:
        sys.exit("Install the loader first: pip install datasets")
    return [dict(r) for r in load_dataset(DATASET, split=split)]


def select_instances(rows: list[dict], n: int, seed: int) -> list[dict]:
    """Seeded sample stratified by difficulty label (round-robin across strata, then across repos)."""
    if n <= 0:
        raise ValueError("n must be positive")
    rng = random.Random(seed)
    strata: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["instance_id"]):
        strata[r.get("difficulty") or "unlabelled"].append(r)
    for bucket in strata.values():
        rng.shuffle(bucket)
    order = sorted(strata)
    chosen: list[dict] = []
    seen_repos: dict[str, int] = defaultdict(int)
    while len(chosen) < n and any(strata.values()):
        for key in order:
            bucket = strata[key]
            if not bucket or len(chosen) >= n:
                continue
            # prefer the least-used repository inside this stratum
            bucket.sort(key=lambda r: seen_repos[r["repo"]])
            pick = bucket.pop(0)
            seen_repos[pick["repo"]] += 1
            chosen.append(pick)
    return chosen


def select_by_ids(rows: list[dict], candidates: list[dict]) -> list[dict]:
    """Keep the dataset rows named in a candidate list (e.g. swebench_pilot/candidates.json), in its order,
    carrying the candidate's empirical-difficulty tier. Every ID must exist in the dataset."""
    by_id = {r["instance_id"]: r for r in rows}
    missing = [c["instance_id"] for c in candidates if c["instance_id"] not in by_id]
    if missing:
        raise ValueError(f"candidate IDs not in {DATASET}: {missing}")
    return [{**by_id[c["instance_id"]], "difficulty": by_id[c["instance_id"]].get("difficulty"), "tier": c.get("tier")} for c in candidates]


def _count(field) -> int | None:
    """FAIL_TO_PASS / PASS_TO_PASS are JSON-encoded lists in the dataset."""
    if field is None:
        return None
    return len(json.loads(field) if isinstance(field, str) else field)


def manifest_entry(r: dict) -> dict:
    return {
        "instance_id": r["instance_id"],
        "repo": r["repo"],
        "base_commit": r["base_commit"],
        "difficulty": r.get("difficulty"),
        "tier": r.get("tier"),
        "fail_to_pass_count": _count(r.get("FAIL_TO_PASS")),
        "pass_to_pass_count": _count(r.get("PASS_TO_PASS")),
        "problem_statement_sha256": hashlib.sha256(r["problem_statement"].encode("utf-8")).hexdigest(),
        "problem_statement": r["problem_statement"],
    }


def write_manifest(path: Path, entries: list[dict], seed: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"dataset": DATASET, "seed": seed, "instances": entries}, indent=2), encoding="utf-8")


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for e in data["instances"]:
        digest = hashlib.sha256(e["problem_statement"].encode("utf-8")).hexdigest()
        if digest != e["problem_statement_sha256"]:
            raise ValueError(f"manifest entry {e['instance_id']} was edited (problem statement hash mismatch)")
    return data


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def prepare(manifest: dict, assistant: str, root: Path, time_limit: int, clone_url: str = "https://github.com/{repo}.git") -> list[Path]:
    made = []
    for e in manifest["instances"]:
        ws = root / assistant / e["instance_id"]
        if ws.exists():
            print(f"skip {ws} (exists)")
            made.append(ws)
            continue
        ws.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "--quiet", clone_url.format(repo=e["repo"]), str(ws))
        git("checkout", "--quiet", e["base_commit"], cwd=ws)
        task = TASK_TEMPLATE.format(time_limit=time_limit, **e)
        (ws / "PILOT_TASK.md").write_text(task, encoding="utf-8")
        made.append(ws)
        print(f"prepared {ws}")
    return made


def collect(manifest: dict, assistant: str, root: Path) -> list[dict]:
    preds = []
    for e in manifest["instances"]:
        ws = root / assistant / e["instance_id"]
        if not ws.exists():
            patch = ""
        else:
            git("add", "-A", "--", ".", ":(exclude)PILOT_TASK.md", cwd=ws)
            patch = git("diff", "--cached", e["base_commit"], "--", ".", ":(exclude)PILOT_TASK.md", cwd=ws)
            git("reset", "--quiet", cwd=ws)
        preds.append({"instance_id": e["instance_id"], "model_name_or_path": assistant, "model_patch": patch})
    return preds


def evaluate(predictions: Path, run_id: str, workers: int) -> int:
    cmd = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        DATASET,
        "--predictions_path",
        str(predictions),
        "--max_workers",
        str(workers),
        "--run_id",
        run_id,
    ]
    print(" ".join(cmd))
    return subprocess.call(cmd)


def summarize(report_paths: list[Path]) -> list[dict]:
    """Read harness reports (<model>.<run_id>.json) into one row per assistant."""
    rows = []
    for p in sorted(report_paths):
        rep = json.loads(p.read_text(encoding="utf-8"))
        if "resolved_ids" not in rep:
            continue
        submitted = rep.get("submitted_instances", rep.get("total_instances"))
        resolved = len(rep["resolved_ids"])
        rows.append(
            {
                "assistant": p.name.split(".")[0],
                "submitted": submitted,
                "resolved": resolved,
                "empty_patch": len(rep.get("empty_patch_ids", [])),
                "error": len(rep.get("error_ids", [])),
                "resolve_rate": round(resolved / submitted, 4) if submitted else None,
                "report": p.name,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SWE-bench Verified pilot (human-operated)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--n", type=int, default=12)
    s.add_argument("--seed", type=int, default=2026)
    s.add_argument("--out", type=Path, default=Path("swebench_pilot/manifest.json"))
    s.add_argument(
        "--ids-from",
        type=Path,
        help="candidate list (default design: swebench_pilot/candidates.json, stratified by leaderboard difficulty)",
    )
    for name in ("prepare", "collect"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--assistant", choices=ASSISTANTS, required=True)
        p.add_argument("--workspaces", type=Path, required=True)
        if name == "prepare":
            p.add_argument("--time-limit", type=int, default=30, help="minutes per instance")
        else:
            p.add_argument("--out", type=Path, required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--predictions", type=Path, required=True)
    e.add_argument("--run-id", required=True)
    e.add_argument("--workers", type=int, default=2)
    m = sub.add_parser("summarize")
    m.add_argument("--reports-dir", type=Path, default=Path("."))
    m.add_argument("--out", type=Path, default=Path("swebench_pilot/results.csv"))
    args = ap.parse_args(argv)

    if args.cmd == "select":
        rows = load_dataset_rows()
        if args.ids_from:
            chosen = select_by_ids(rows, json.loads(args.ids_from.read_text(encoding="utf-8"))["instances"])
        else:
            chosen = select_instances(rows, args.n, args.seed)
        write_manifest(args.out, [manifest_entry(r) for r in chosen], args.seed)
        print(f"wrote {len(chosen)} instances to {args.out}")
    elif args.cmd == "prepare":
        prepare(read_manifest(args.manifest), args.assistant, args.workspaces.expanduser(), args.time_limit)
    elif args.cmd == "collect":
        preds = collect(read_manifest(args.manifest), args.assistant, args.workspaces.expanduser())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(p) + "\n" for p in preds), encoding="utf-8")
        print(f"wrote {len(preds)} predictions ({sum(1 for p in preds if p['model_patch'])} non-empty) to {args.out}")
    elif args.cmd == "evaluate":
        return evaluate(args.predictions, args.run_id, args.workers)
    elif args.cmd == "summarize":
        rows = summarize(list(args.reports_dir.glob("*.json")))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["assistant", "submitted", "resolved", "empty_patch", "error", "resolve_rate", "report"])
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
