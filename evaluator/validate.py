"""Executable validation of benchmark tasks.

For every task this checks that:
* metadata is complete and the prompt does not leak hidden grading or reference material;
* the starter workspace FAILS the acceptance criteria (the task is not already solved);
* the starter + reference overlay PASSES acceptance and regression tests (the task is solvable);
* the reference solution only touches in-scope files;
* for test-writing tasks, the reference suite kills every mutant (no equivalent mutants).

Results are written to ``benchmark_tasks/_validation/<TASK_ID>.json`` together with the task hash,
so that a later change to the task marks the validation as stale.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from evaluator import EVALUATOR_VERSION
from evaluator.evaluate import evaluate, utc_now
from evaluator.paths import VALIDATION_DIR
from evaluator.tasks import Task, iter_files
from evaluator.workspace import create_workspace

LEAK_MARKERS = ("grading/", "reference/", "mutant", "_acb", "_validation", "hidden test")


def _short(report: Dict[str, Any]) -> Dict[str, Any]:
    acc = report.get("acceptance") or {}
    reg = report.get("regression") or {}
    return {
        "status": report.get("status"),
        "success": report.get("success"),
        "outcome": report.get("outcome"),
        "error": report.get("error"),
        "acceptance": {k: acc.get(k) for k in ("status", "passed", "failed", "errors", "skipped", "total")},
        "regression": {k: reg.get(k) for k in ("status", "passed", "failed", "errors", "skipped", "total")},
        "out_of_scope_files": (report.get("diff") or {}).get("out_of_scope_files"),
        "test_quality": {
            k: (report.get("test_quality") or {}).get(k)
            for k in ("tests_collected", "line_coverage", "mutation_score", "mutants_killed", "mutants_total")
        }
        if report.get("test_quality")
        else None,
        "ruff_new": (report.get("ruff") or {}).get("new_count"),
        "semgrep_status": (report.get("semgrep") or {}).get("status"),
        "semgrep_baseline": (report.get("semgrep") or {}).get("baseline_count"),
        "semgrep_submission": (report.get("semgrep") or {}).get("submission_count"),
    }


def static_checks(task: Task) -> List[Dict[str, Any]]:
    checks = []
    prompt = task.prompt()
    lowered = prompt.lower()
    leaks = [marker for marker in LEAK_MARKERS if marker in lowered]
    checks.append({"id": "prompt_no_leak_markers", "passed": not leaks, "detail": f"prompt mentions: {leaks}" if leaks else None})
    checks.append({"id": "prompt_not_empty", "passed": len(prompt.strip()) > 200, "detail": None})
    grading_digests = {p.read_bytes().replace(b"\r\n", b"\n") for p in iter_files(task.grading_dir)}
    reference_digests = {p.read_bytes().replace(b"\r\n", b"\n") for p in iter_files(task.reference_dir)}
    leaked = sorted(
        p.relative_to(task.starter_dir).as_posix()
        for p in iter_files(task.starter_dir)
        if p.suffix == ".py" and p.stat().st_size > 0 and p.read_bytes().replace(b"\r\n", b"\n") in (grading_digests | reference_digests)
    )
    checks.append({"id": "starter_contains_no_hidden_material", "passed": not leaked, "detail": leaked or None})
    identical = []
    for ref in iter_files(task.reference_dir):
        rel = ref.relative_to(task.reference_dir)
        starter_file = task.starter_dir / rel
        if starter_file.exists() and starter_file.read_bytes() == ref.read_bytes():
            identical.append(rel.as_posix())
    checks.append(
        {"id": "reference_differs_from_starter", "passed": not identical, "detail": f"identical files: {identical}" if identical else None}
    )
    return checks


def validate_task(task: Task, mode: str, write: bool = True) -> Dict[str, Any]:
    checks = static_checks(task)
    with tempfile.TemporaryDirectory(prefix="acb-validate-") as tmp:
        tmp_path = Path(tmp)
        starter_ws = create_workspace(task, tmp_path / "starter_ws")
        starter_report = evaluate(task.id, starter_ws, tmp_path / "starter_out", mode)
        reference_ws = create_workspace(task, tmp_path / "reference_ws")
        for ref in iter_files(task.reference_dir):
            target = reference_ws / ref.relative_to(task.reference_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ref, target)
        reference_report = evaluate(task.id, reference_ws, tmp_path / "reference_out", mode)

    s_acc = starter_report.get("acceptance") or {}
    r_reg = reference_report.get("regression") or {}
    s_reg = starter_report.get("regression") or {}
    checks.append(
        {"id": "starter_evaluation_completed", "passed": starter_report["status"] == "completed", "detail": starter_report.get("error")}
    )
    checks.append(
        {
            "id": "reference_evaluation_completed",
            "passed": reference_report["status"] == "completed",
            "detail": reference_report.get("error"),
        }
    )
    checks.append(
        {
            "id": "starter_fails_acceptance",
            "passed": starter_report.get("success") is False
            and (s_acc.get("failed", 0) + s_acc.get("errors", 0) >= 1 or s_acc.get("status") != "ran"),
            "detail": _short(starter_report)["acceptance"],
        }
    )
    checks.append(
        {
            "id": "reference_passes_acceptance",
            "passed": reference_report.get("success") is True,
            "detail": _short(reference_report)["acceptance"],
        }
    )
    checks.append(
        {
            "id": "reference_passes_regression",
            "passed": r_reg.get("status") == "none" or (r_reg.get("failed") == 0 and r_reg.get("errors") == 0),
            "detail": _short(reference_report)["regression"],
        }
    )
    checks.append(
        {
            "id": "starter_passes_regression",
            "passed": s_reg.get("status") == "none" or (s_reg.get("failed") == 0 and s_reg.get("errors") == 0),
            "detail": _short(starter_report)["regression"],
            "severity": "warning",
        }
    )
    ref_scope = (reference_report.get("diff") or {}).get("out_of_scope_files") or []
    checks.append({"id": "reference_within_scope", "passed": not ref_scope, "detail": ref_scope or None})
    if task.kind == "test_writing":
        tq = reference_report.get("test_quality") or {}
        checks.append(
            {
                "id": "reference_kills_all_mutants",
                "passed": tq.get("mutants_total") is not None and tq.get("mutants_killed") == tq.get("mutants_total"),
                "detail": {"killed": tq.get("mutants_killed"), "total": tq.get("mutants_total")},
            }
        )

    blocking = [c for c in checks if not c["passed"] and c.get("severity") != "warning"]
    hashes = task.hashes()
    record = {
        "task_id": task.id,
        "task_version": task.meta["version"],
        "test_version": task.meta["test_version"],
        "task_hash": hashes["task_hash"],
        "prompt_hash": hashes["prompt_hash"],
        "test_hash": hashes["test_hash"],
        "reference_hash": hashes["reference_hash"],
        "passed": not blocking,
        "validated_at": utc_now(),
        "evaluator_version": EVALUATOR_VERSION,
        "execution_mode": mode,
        "expected_acceptance_total": (reference_report.get("acceptance") or {}).get("total"),
        "checks": checks,
        "starter": _short(starter_report),
        "reference": _short(reference_report),
        "environment": reference_report.get("environment"),
        "manual_review_required": [
            "Prompt read by a second team member for ambiguity (see docs/experimental-protocol.md, section 3).",
        ],
    }
    if write:
        VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
        (VALIDATION_DIR / f"{task.id}.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return record
