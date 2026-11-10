"""Tests for analysis/analyze.py. All records here are synthetic test fixtures, not results."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("analyze", ROOT / "analysis" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)

COLUMNS = [
    "run_id",
    "is_effective_run",
    "eligible_for_success",
    "status",
    "success",
    "timed_out",
    "regression_failure",
    "assistant_id",
    "task_id",
    "task_category",
    "attempt_number",
    "wall_clock_seconds",
    "iterations",
    "human_interventions",
    "ruff_status",
    "ruff_new",
    "semgrep_status",
    "semgrep_new",
    "eval_mode",
    "run_number",
]


def write_csv(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})


def fixture_rows():
    rows = []
    tasks = [f"T-{i:02d}" for i in range(6)]
    pattern = {"a": [1, 1, 1, 1, 0, 1], "b": [0, 0, 1, 0, 0, 0], "c": [1, 0, 1, 1, 1, 0]}
    n = 0
    for assistant, outcomes in pattern.items():
        for task, ok in zip(tasks, outcomes):
            n += 1
            rows.append(
                {
                    "run_id": f"r{n}",
                    "is_effective_run": "true",
                    "eligible_for_success": "true",
                    "status": "completed",
                    "success": "true" if ok else "false",
                    "timed_out": "false",
                    "regression_failure": "false",
                    "assistant_id": assistant,
                    "task_id": task,
                    "task_category": "bug_fixing",
                    "attempt_number": 1,
                    "wall_clock_seconds": 60 * (n % 7 + 1),
                    "iterations": 1 + n % 3,
                    "human_interventions": n % 2,
                    "ruff_status": "ran",
                    "ruff_new": 0,
                    "semgrep_status": "unavailable",
                    "eval_mode": "docker",
                    "run_number": 1,
                }
            )
    rows.append(
        {
            "run_id": "r-failed",
            "is_effective_run": "true",
            "eligible_for_success": "false",
            "status": "failed",
            "assistant_id": "a",
            "task_id": "T-09",
            "task_category": "bug_fixing",
            "attempt_number": 1,
            "run_number": 1,
        }
    )
    rows.append(
        {
            "run_id": "r-old",
            "is_effective_run": "false",
            "eligible_for_success": "false",
            "status": "failed",
            "assistant_id": "b",
            "task_id": "T-00",
            "task_category": "bug_fixing",
            "attempt_number": 1,
            "run_number": 1,
        }
    )
    return rows


def test_empty_export_produces_explicit_message(tmp_path):
    path = tmp_path / "results.csv"
    write_csv(path, [])
    result = analyze.run([path], tmp_path / "out")
    assert result["status"] == "empty"
    report = (tmp_path / "out" / "REPORT.md").read_text()
    assert "No eligible experimental records" in report
    assert not (tmp_path / "out" / "summary_by_assistant.csv").exists()


def test_only_unfinished_runs_is_still_empty(tmp_path):
    path = tmp_path / "results.csv"
    write_csv(path, [r for r in fixture_rows() if r["run_id"] == "r-failed"])
    assert analyze.run([path], tmp_path / "out")["status"] == "empty"
    assert (tmp_path / "out" / "missing_data.csv").exists()


def test_descriptive_and_inferential_outputs(tmp_path):
    path = tmp_path / "results.csv"
    write_csv(path, fixture_rows())
    result = analyze.run([path], tmp_path / "out")
    assert result["status"] == "ok"
    assert result["eligible"] == 18
    with open(tmp_path / "out" / "summary_by_assistant.csv", encoding="utf-8") as handle:
        rows = {r["assistant_id"]: r for r in csv.DictReader(handle)}
    assert rows["a"]["successes"] == "5" and rows["a"]["n_completed"] == "6"
    assert abs(float(rows["b"]["success_rate"]) - 1 / 6) < 1e-9
    tests = json.loads((tmp_path / "out" / "inferential_tests.json").read_text())
    assert tests["status"] == "computed"
    assert tests["complete_blocks"] == 6
    assert len(tests["pairwise_mcnemar_exact"]) == 3
    assert 0 <= tests["cochran_q"]["p_value"] <= 1
    assert (tmp_path / "out" / "success_by_assistant.png").exists()
    with open(tmp_path / "out" / "missing_data.csv", encoding="utf-8") as handle:
        missing = {r["assistant_id"]: r for r in csv.DictReader(handle)}
    assert missing["a"]["failed"] == "1"  # superseded run r-old is not counted


def test_wilson_and_holm():
    low, high = analyze.wilson(18, 36)
    assert 0.33 < low < 0.35 and 0.65 < high < 0.67
    assert analyze.wilson(5, 5)[1] == 1.0
    assert analyze.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_cochran_q_matches_textbook_example():
    import pandas as pd

    # Example data: 3 treatments, 12 subjects (Conover style), Q computed by hand = 8.0
    data = pd.DataFrame(
        {
            "x": [1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1],
            "y": [1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
            "z": [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        }
    )
    k = 3
    col = data.sum()
    row = data.sum(axis=1)
    expected = (k - 1) * (k * (col**2).sum() - row.sum() ** 2) / (k * row.sum() - (row**2).sum())
    assert abs(analyze.cochran_q(data)["q"] - expected) < 1e-9


def test_mixed_benchmarks_must_be_analysed_separately(tmp_path):
    import pandas as pd

    from analysis import analyze

    rows = [
        {"run_id": "a", "is_effective_run": True, "eligible_for_success": False, "status": "planned", "task_benchmark": "custom"},
        {
            "run_id": "b",
            "is_effective_run": True,
            "eligible_for_success": False,
            "status": "planned",
            "task_benchmark": "swebench_verified",
        },
    ]
    f = tmp_path / "mixed.csv"
    pd.DataFrame(rows).to_csv(f, index=False)
    import pytest

    with pytest.raises(SystemExit, match="mixes benchmarks"):
        analyze.run([f], tmp_path / "o")
    single = tmp_path / "single.csv"
    pd.DataFrame(rows[:1]).drop(columns=["is_effective_run"]).to_csv(single, index=False)
    assert analyze.run([single], tmp_path / "o2")["status"] == "empty"  # one benchmark: no error
