"""Export golden tasks the main app can run today into ``dataset/app_swebench_verified.json``.

The app (evaluator/swebench.py) scores SWE-bench Verified instances with the official harness, so
the golden tasks it can use are the FAIL_TO_PASS tasks drawn from Verified. Entries follow the
``swebench_pilot/manifest.json`` format (same problem-statement hash check), plus golden fields:
domain, subdomain, calibrated difficulty and the gold patch's QualityScore.
Tasks from the other sources stay in the dataset files: they need harness images the app does not build.
"""
from __future__ import annotations

import hashlib
import json
import os

APP_SOURCE = "swebench_verified"
APP_FILE = "app_swebench_verified.json"


def _as_list(v):
    return v if isinstance(v, list) else json.loads(v) if v else []


def export_app_tasks(golden_jsonl: str, out_dir: str, version: str) -> str:
    with open(golden_jsonl, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    entries = []
    for r in rows:
        if r["source"] != APP_SOURCE or r["eval_type"] != "fail_to_pass":
            continue
        ps = r["problem_statement"]
        cq = r.get("code_quality") or {}
        entries.append({
            "instance_id": r["source_instance_id"],
            "golden_task_id": r["task_id"],
            "repo": r["repo"],
            "base_commit": r["base_commit"],
            "difficulty": (r.get("metadata") or {}).get("time_estimate"),
            "tier": r["difficulty"],
            "domain": r["domain"],
            "subdomain": r.get("subdomain"),
            "domain_confidence": r.get("domain_confidence"),
            "gold_quality_score": cq.get("quality_score"),
            "gate_flags": r.get("gate_flags") or [],
            "fail_to_pass_count": len(_as_list(r.get("fail_to_pass"))),
            "pass_to_pass_count": len(_as_list(r.get("pass_to_pass"))),
            "problem_statement_sha256": hashlib.sha256(ps.encode("utf-8")).hexdigest(),
            "problem_statement": ps,
        })
    entries.sort(key=lambda e: (e["domain"], e["tier"], e["instance_id"]))
    path = os.path.join(out_dir, APP_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"dataset": "princeton-nlp/SWE-bench_Verified", "benchmark": "golden_verified",
                   "golden_version": version, "instances": entries}, fh, indent=2)
    return path
