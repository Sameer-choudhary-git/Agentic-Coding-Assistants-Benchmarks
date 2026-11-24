"""Smoke-test the app's scoring on golden tasks by submitting each task's *reference fix*.

For every task id: clone the repository at the base commit (the same workspace the app gives an assistant),
apply the reference fix from the golden JSONL, and score it with ``evaluator.swebench.evaluate`` (hidden tests in
Docker + patch code quality). A correctly working harness must report every reference fix as resolved; anything
else means the scoring setup (Docker image, dataset split, Pro scripts) is broken for that task.

Optional ``--negative``: also score a patch that only adds a comment to a touched file. It must NOT resolve, which
shows that the FAIL_TO_PASS tests really fail without the fix.

Run from WSL (the SWE-bench harness does not support native Windows):
    ACB_SWEBENCH_PRO_SCRIPTS=~/SWE-bench_Pro-os/run_scripts \\
    ~/acb-venv/bin/python golden/scripts/smoke_harness.py --work ~/acb-smoke <app task id> ...
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluator import swebench as S  # noqa: E402


def gold_patches() -> dict:
    out = {}
    with open(ROOT / "golden" / "dataset" / "golden_v1.0.0.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            out[r["source_instance_id"]] = r.get("gold_patch") or ""
    return out


def negative_patch(gold: str) -> tuple[str, str] | None:
    """A harmless edit to the first touched .py/.js/.ts/.go/.rb/.rs/.c file: a trailing comment line."""
    for line in gold.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            ext = path.rsplit(".", 1)[-1]
            mark = {"py": "#", "rb": "#"}.get(ext, "//" if ext in ("js", "ts", "tsx", "jsx", "go", "rs", "c", "h", "java") else None)
            if mark:
                return path, f"{mark} acb smoke negative control"
    return None


def run(task_id: str, work: Path, gold: dict, negative: bool) -> dict:
    inst = S.get_instance(task_id)
    src_id = inst.get("source_instance_id") or task_id
    patch = gold.get(src_id)
    if not patch:
        return {"task": task_id, "error": "no reference fix in the golden JSONL"}
    results = {"task": task_id, "source": (inst.get("golden") or {}).get("source"), "harness": S.harness_type(inst)}
    variants = [("reference_fix", patch)]
    if negative:
        variants.append(("negative_control", None))
    for name, p in variants:
        ws = work / f"{task_id}-{name}"
        out = work / f"{task_id}-{name}-out"
        for d in (ws, out):
            shutil.rmtree(d, ignore_errors=True)
        S.create_workspace(task_id, ws)
        if p is not None:
            (ws / "_gold.diff").write_text(p, encoding="utf-8", newline="\n")
            subprocess.run(["git", "apply", "--whitespace=nowarn", "_gold.diff"], cwd=ws, check=True)
            (ws / "_gold.diff").unlink()
        else:
            target = negative_patch(patch)
            if not target:
                results[name] = {"skipped": "no editable source file"}
                continue
            path, text = target
            with open(ws / path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n" + text + "\n")
        t0 = time.monotonic()
        rep = S.evaluate(task_id, ws, out, run_context={"run_id": f"smoke-{name}-{int(time.time())}", "assistant_id": "reference"})
        cq = rep.get("code_quality") or {}
        results[name] = {
            "outcome": rep.get("outcome"),
            "resolved": rep.get("success"),
            "error": rep.get("error"),
            "fail_to_pass": f"{(rep.get('acceptance') or {}).get('passed')}/{(rep.get('acceptance') or {}).get('total')}",
            "pass_to_pass_failed": (rep.get("regression") or {}).get("failed"),
            "quality": cq.get("quality_score"),
            "quality_status": cq.get("status"),
            "gold_quality_score": cq.get("gold_quality_score"),
            "seconds": round(time.monotonic() - t0),
            "report": str(out / "report.json"),
        }
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--work", type=Path, default=Path.home() / "acb-smoke")
    ap.add_argument("--negative", action="store_true")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    gold = gold_patches()
    for t in a.tasks:
        try:
            r = run(t, a.work, gold, a.negative)
        except Exception as exc:  # noqa: BLE001
            r = {"task": t, "error": f"{type(exc).__name__}: {exc}"[:800]}
        print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
