"""End-to-end evaluator behaviour, including failure paths. Uses the local execution mode."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

import evaluator.evaluate as evaluate_module
from evaluator.cli import main as cli_main
from evaluator.evaluate import evaluate
from evaluator.runner import parse_junit
from evaluator.tasks import get_task, iter_files
from evaluator.workspace import create_workspace


def apply_reference(task, ws: Path) -> None:
    for ref in iter_files(task.reference_dir):
        target = ws / ref.relative_to(task.reference_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ref, target)


@pytest.fixture()
def bf01(tmp_path):
    task = get_task("BF-01")
    return task, create_workspace(task, tmp_path / "ws")


def test_starter_fails_and_report_is_complete(bf01, tmp_path):
    task, ws = bf01
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["status"] == "completed"
    assert report["success"] is False
    assert report["outcome"] == "acceptance_failed"
    assert report["acceptance"]["failed"] >= 1
    assert report["regression"]["failed"] == 0
    assert report["task"]["task_hash"] == task.hashes()["task_hash"]
    assert report["environment"]["execution"]["mode"] == "local"
    assert report["ruff"]["status"] in ("ran", "unavailable")
    assert report["semgrep"]["status"] in ("ran", "unavailable", "error")
    saved = json.loads((tmp_path / "out" / "report.json").read_text())
    assert saved["outcome"] == "acceptance_failed"
    assert (tmp_path / "out" / "acceptance.xml").exists()


def test_reference_passes_with_patch_artifact(bf01, tmp_path):
    task, ws = bf01
    apply_reference(task, ws)
    report = evaluate("BF-01", ws, tmp_path / "out", "local", expected_task_hash=task.hashes()["task_hash"])
    assert report["success"] is True
    assert report["outcome"] == "passed"
    assert report["integrity"]["task_hash_matches"] is True
    assert report["diff"]["files_changed"] == 1
    patch = (tmp_path / "out" / "submission.patch").read_text()
    assert patch.startswith("--- a/pager/paginate.py")


def test_task_hash_mismatch_is_an_error(bf01, tmp_path):
    _, ws = bf01
    report = evaluate("BF-01", ws, tmp_path / "out", "local", expected_task_hash="0" * 64)
    assert report["status"] == "error"
    assert report["error"]["class"] == "task_hash_mismatch"
    assert report["success"] is None


def test_missing_workspace_reports_error(tmp_path):
    report = evaluate("BF-01", tmp_path / "nope", tmp_path / "out", "local")
    assert report["status"] == "error"
    assert report["error"]["class"] == "workspace_invalid"


def test_unknown_task_reports_error(tmp_path):
    report = evaluate("XX-99", tmp_path, tmp_path / "out", "local")
    assert report["error"]["class"] == "task_error"


def test_unknown_mode_reports_unavailable(bf01, tmp_path):
    _, ws = bf01
    report = evaluate("BF-01", ws, tmp_path / "out", "remote")
    assert report["error"]["class"] == "execution_unavailable"


def test_infinite_loop_is_a_timeout_not_a_crash(bf01, tmp_path, monkeypatch):
    task, ws = bf01
    fast = copy.deepcopy(task)
    fast.meta["test_timeout_seconds"] = 3
    monkeypatch.setattr(evaluate_module, "get_task", lambda _id: fast)
    (ws / "pager" / "paginate.py").write_text(
        "from dataclasses import dataclass\n\n@dataclass\nclass Page:\n    items: list\n\n"
        "def paginate(items, page, per_page):\n    while True:\n        pass\n"
    )
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["status"] == "completed"
    assert report["success"] is False
    assert report["outcome"] == "test_timeout"
    assert report["acceptance"]["process"]["timed_out"] is True


def test_syntax_error_submission_is_collection_error(bf01, tmp_path):
    _, ws = bf01
    (ws / "pager" / "paginate.py").write_text("def broken(:\n")
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["success"] is False
    assert report["outcome"] == "collection_error"


def test_conftest_cannot_force_passing_results(bf01, tmp_path):
    _, ws = bf01
    (ws / "conftest.py").write_text(
        "import pytest\n\n@pytest.hookimpl(hookwrapper=True)\ndef pytest_runtest_makereport(item, call):\n"
        "    outcome = yield\n    rep = outcome.get_result()\n    rep.outcome = 'passed'\n"
    )
    (ws / "pager" / "conftest.py").write_text((ws / "conftest.py").read_text())
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["success"] is False
    assert "conftest.py" in report["sandbox_actions"]["removed_harness_files"]
    assert "conftest.py" in report["diff"]["harness_sensitive_files"]


def test_tests_cannot_be_deleted_to_pass(bf01, tmp_path):
    task, ws = bf01
    apply_reference(task, ws)
    shutil.rmtree(ws / "tests")
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    # Hidden tests live outside the workspace, so deleting visible tests changes nothing.
    assert report["success"] is True
    assert {c["path"] for c in report["diff"]["changed_files"]} >= {"tests/test_smoke.py"}


def test_missing_static_tools_are_reported_not_zero(bf01, tmp_path, monkeypatch):
    _, ws = bf01
    monkeypatch.setenv("ACB_RUFF_BIN", "definitely-not-a-real-ruff")
    monkeypatch.setenv("ACB_SEMGREP_BIN", "definitely-not-a-real-semgrep")
    monkeypatch.setenv("PATH", "")
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["ruff"]["status"] == "unavailable"
    assert report["ruff"].get("submission_count") is None
    assert report["semgrep"]["status"] == "unavailable"
    assert report["semgrep"].get("submission_count") is None


def test_ruff_new_findings_are_relative_to_baseline(bf01, tmp_path):
    if shutil.which("ruff") is None:
        pytest.skip("ruff not installed")
    task, ws = bf01
    apply_reference(task, ws)
    path = ws / "pager" / "paginate.py"
    path.write_text(path.read_text() + "\n\nimport os\n")
    report = evaluate("BF-01", ws, tmp_path / "out", "local")
    assert report["ruff"]["status"] == "ran"
    new_codes = {f["code"] for f in report["ruff"]["new_findings"]}
    assert "F401" in new_codes
    assert report["success"] is True  # static findings never change success


def test_test_writing_quality_metrics(tmp_path):
    task = get_task("TW-01")
    ws = create_workspace(task, tmp_path / "ws")
    (ws / "tests" / "test_weak.py").write_text(
        "from textstats.stats import word_count\n\n" + "".join(f"def test_{i}():\n    assert word_count('a b') == 2\n\n" for i in range(6))
    )
    weak = evaluate("TW-01", ws, tmp_path / "weak", "local")
    tq = weak["test_quality"]
    assert weak["success"] is False
    assert tq["tests_collected"] == 6
    assert tq["line_coverage"] < 0.9
    assert tq["mutation_score"] < 0.8
    outcomes = {c["id"]: c["outcome"] for c in weak["acceptance"]["tests"]}
    assert outcomes == {
        "tests_pass_on_original": "passed",
        "min_test_count": "passed",
        "line_coverage": "failed",
        "mutation_score": "failed",
    }

    apply_reference(task, ws)
    (ws / "tests" / "test_weak.py").unlink()
    strong = evaluate("TW-01", ws, tmp_path / "strong", "local")
    assert strong["success"] is True
    assert strong["test_quality"]["mutation_score"] == 1.0


def test_test_writing_failing_suite_gets_no_mutation_credit(tmp_path):
    task = get_task("TW-02")
    ws = create_workspace(task, tmp_path / "ws")
    (ws / "tests" / "test_fail.py").write_text("def test_always_fails():\n    assert False\n")
    report = evaluate("TW-02", ws, tmp_path / "out", "local")
    assert report["success"] is False
    assert report["test_quality"]["mutation_score"] is None


def test_parse_junit_handles_missing_and_corrupt(tmp_path):
    assert parse_junit(tmp_path / "missing.xml") is None
    bad = tmp_path / "bad.xml"
    bad.write_text("<testsuite><testcase")
    assert parse_junit(bad) is None


def test_cli_evaluate_exit_codes(bf01, tmp_path, capsys):
    _, ws = bf01
    code = cli_main(["evaluate", "--task", "BF-01", "--workspace", str(ws), "--out", str(tmp_path / "o"), "--mode", "local"])
    assert code == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["outcome"] == "acceptance_failed"
    code = cli_main(["evaluate", "--task", "BF-01", "--workspace", str(tmp_path / "x"), "--out", str(tmp_path / "o2"), "--mode", "local"])
    assert code == 2
