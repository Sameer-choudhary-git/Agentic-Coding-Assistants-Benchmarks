"""Evaluate one submitted workspace for one task and produce a machine-readable report."""

from __future__ import annotations

import json
import platform
import shutil
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from evaluator import EVALUATOR_VERSION, REPORT_SCHEMA_VERSION
from evaluator.runner import ExecutionUnavailable, Executor, PytestOutcome, make_executor
from evaluator.static_analysis import analyse_ruff, analyse_semgrep
from evaluator.tasks import TaskError, get_task
from evaluator.test_quality import evaluate_test_writing
from evaluator.workspace import Snapshot, WorkspaceError, diff_snapshots, prepare_eval_dir, snapshot


class EvaluationError(Exception):
    def __init__(self, error_class: str, message: str) -> None:
        super().__init__(message)
        self.error_class = error_class


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_snapshot(snap: Snapshot, root: Path) -> None:
    for rel, data in snap.files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def summarize_pytest(outcome: PytestOutcome, expected_total: Optional[int]) -> Dict[str, Any]:
    if outcome.proc.error:
        status = "error"
    elif outcome.proc.timed_out:
        status = "timeout"
    elif outcome.collection_error:
        status = "collection_error"
    elif not outcome.junit_found:
        status = "error"
    else:
        status = "ran"
    collected = outcome.total
    missing = max(0, (expected_total or 0) - collected) if expected_total else 0
    return {
        "status": status,
        "passed": outcome.passed,
        "failed": outcome.failed,
        "errors": outcome.errors,
        "skipped": outcome.skipped,
        "total": collected,
        "expected_total": expected_total,
        "missing": missing,
        "tests": outcome.tests,
        "process": outcome.proc.to_dict(),
    }


def _save_proc_output(artifacts: Path, stem: str, outcome: PytestOutcome) -> None:
    (artifacts / f"{stem}.stdout.txt").write_text(outcome.proc.stdout, encoding="utf-8")
    (artifacts / f"{stem}.stderr.txt").write_text(outcome.proc.stderr, encoding="utf-8")


def decide(acceptance: Dict[str, Any], regression: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the documented task-success rule. Returns success flag and outcome category."""
    if acceptance["status"] == "error" or regression.get("status") == "error":
        return {"success": None, "outcome": "evaluator_error"}
    if acceptance["status"] == "timeout" or regression.get("status") == "timeout":
        return {"success": False, "outcome": "test_timeout"}
    if acceptance["status"] == "collection_error":
        return {"success": False, "outcome": "collection_error"}
    acceptance_ok = (
        acceptance["failed"] == 0
        and acceptance["errors"] == 0
        and acceptance.get("missing", 0) == 0
        and acceptance["passed"] >= 1
        and acceptance["passed"] + acceptance["skipped"] == acceptance["total"]
    )
    regression_ok = regression.get("status") == "none" or (
        regression.get("status") == "ran" and regression["failed"] == 0 and regression["errors"] == 0
    )
    if regression.get("status") == "collection_error":
        regression_ok = False
    if not acceptance_ok:
        return {"success": False, "outcome": "acceptance_failed"}
    if not regression_ok:
        return {"success": False, "outcome": "regression_failed"}
    return {"success": True, "outcome": "passed"}


def evaluate(
    task_id: str,
    workspace: Path,
    out_dir: Path,
    mode: str,
    expected_task_hash: Optional[str] = None,
    run_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_wall = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "status": "error",
        "error": None,
        "success": None,
        "outcome": "evaluator_error",
        "execution_mode": mode,
        "started_at": started_wall.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "finished_at": None,
        "duration_s": None,
        "run_context": run_context or {},
        "task": {"id": task_id},
        "integrity": {},
        "workspace": {"name": workspace.name},
        "diff": None,
        "sandbox_actions": None,
        "acceptance": None,
        "regression": None,
        "test_quality": None,
        "ruff": None,
        "semgrep": None,
        "environment": {
            "host_platform": platform.platform(),
            "host_python": sys.version.split()[0],
        },
        "success_rule": (
            "success = acceptance checks all pass (none failed/errored/missing, >=1 passed) AND no regression "
            "test failed AND tests completed within the timeout. Static-analysis findings never change success."
        ),
        "artifacts": {"directory": out_dir.name, "files": []},
    }
    try:
        task = get_task(task_id)
        hashes = task.hashes()
        validation = task.validation_status()
        report["task"] = {
            "id": task.id,
            "title": task.meta["title"],
            "category": task.meta["category"],
            "kind": task.kind,
            "version": task.meta["version"],
            "test_version": task.meta["test_version"],
            "task_hash": hashes["task_hash"],
            "prompt_hash": hashes["prompt_hash"],
            "test_hash": hashes["test_hash"],
            "starter_hash": hashes["starter_hash"],
            "validation_status": validation["status"],
        }
        report["integrity"] = {
            "expected_task_hash": expected_task_hash,
            "task_hash_matches": None if expected_task_hash is None else expected_task_hash == hashes["task_hash"],
        }
        if expected_task_hash and expected_task_hash != hashes["task_hash"]:
            raise EvaluationError(
                "task_hash_mismatch",
                "the task definition changed since this run was created; re-create the run or restore the task version",
            )
        executor: Executor = make_executor(mode)
        report["environment"]["execution"] = executor.describe()

        baseline = snapshot(task.starter_dir)
        submission = snapshot(workspace)
        report["workspace"].update(
            {"snapshot_hash": submission.digest(), "file_count": len(submission.files), "starter_hash": baseline.digest()}
        )
        diff = diff_snapshots(baseline, submission, task)
        (out_dir / "submission.patch").write_text(str(diff.pop("patch")), encoding="utf-8")
        report["diff"] = diff

        with tempfile.TemporaryDirectory(prefix="acb-eval-") as tmp:
            tmp_path = Path(tmp)
            eval_dir = tmp_path / "eval"
            report["sandbox_actions"] = prepare_eval_dir(task, submission, baseline, eval_dir)
            timeout = float(task.meta.get("test_timeout_seconds", 120))
            if task.kind == "test_writing":
                result = evaluate_test_writing(task, executor, eval_dir, out_dir)
                report["acceptance"] = result["acceptance"]
                report["test_quality"] = result["test_quality"]
                report["regression"] = {"status": "none", "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0, "tests": []}
            else:
                acc = executor.run_pytest(eval_dir, ["_acb/grading/acceptance"], "acceptance.xml", timeout)
                _save_proc_output(out_dir, "acceptance", acc)
                expected = validation.get("expected_acceptance_total") if validation["status"] == "validated" else None
                report["acceptance"] = summarize_pytest(acc, expected)
                if (task.grading_dir / "regression").is_dir():
                    reg = executor.run_pytest(eval_dir, ["_acb/grading/regression"], "regression.xml", timeout)
                    _save_proc_output(out_dir, "regression", reg)
                    report["regression"] = summarize_pytest(reg, None)
                else:
                    report["regression"] = {"status": "none", "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0, "tests": []}
            for junit in (eval_dir / "_acb" / "out").glob("*.xml"):
                shutil.copyfile(junit, out_dir / junit.name)
            coverage = eval_dir / "_acb" / "out" / "coverage.json"
            if coverage.exists():
                shutil.copyfile(coverage, out_dir / "coverage.json")

            base_static = tmp_path / "baseline"
            sub_static = tmp_path / "submission"
            _write_snapshot(baseline, base_static)
            _write_snapshot(submission, sub_static)
            base_static.mkdir(exist_ok=True)
            sub_static.mkdir(exist_ok=True)
            report["ruff"] = analyse_ruff(base_static, sub_static)
            report["semgrep"] = analyse_semgrep(base_static, sub_static)

        decision = decide(report["acceptance"], report["regression"])
        report["success"] = decision["success"]
        report["outcome"] = decision["outcome"]
        report["status"] = "completed" if decision["success"] is not None else "error"
        if report["status"] == "error":
            report["error"] = {"class": "evaluator_error", "message": "pytest could not be executed; see artifacts"}
    except TaskError as exc:
        report["error"] = {"class": "task_error", "message": str(exc)}
    except WorkspaceError as exc:
        report["error"] = {"class": "workspace_invalid", "message": str(exc)}
    except ExecutionUnavailable as exc:
        report["error"] = {"class": "execution_unavailable", "message": str(exc)}
    except EvaluationError as exc:
        report["error"] = {"class": exc.error_class, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - every failure must end up in the report
        report["error"] = {"class": "internal_error", "message": f"{type(exc).__name__}: {exc}"}
        (out_dir / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finished = datetime.now(timezone.utc)
    report["finished_at"] = finished.isoformat(timespec="seconds").replace("+00:00", "Z")
    report["duration_s"] = round((finished - started_wall).total_seconds(), 3)
    report["artifacts"]["files"] = sorted(p.name for p in out_dir.iterdir() if p.is_file()) + ["report.json"]
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report
