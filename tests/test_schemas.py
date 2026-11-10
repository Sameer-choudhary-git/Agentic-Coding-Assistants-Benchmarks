"""Schema checks for task metadata and evaluator reports."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from evaluator.evaluate import evaluate
from evaluator.tasks import discover_tasks, get_task
from evaluator.workspace import create_workspace

ROOT = Path(__file__).resolve().parents[1]


def schema(name: str):
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("task", discover_tasks(), ids=lambda t: t.id)
def test_task_metadata_matches_schema(task):
    jsonschema.validate(task.meta, schema("task.schema.json"))
    assert task.root.name.startswith(task.id + "_")


def test_completed_and_error_reports_match_schema(tmp_path):
    report_schema = schema("evaluation-report.schema.json")
    ws = create_workspace(get_task("BF-03"), tmp_path / "ws")
    completed = evaluate("BF-03", ws, tmp_path / "ok", "local")
    jsonschema.validate(completed, report_schema)
    error = evaluate("BF-03", tmp_path / "missing", tmp_path / "err", "local")
    jsonschema.validate(error, report_schema)
    tw = create_workspace(get_task("TW-02"), tmp_path / "tw")
    jsonschema.validate(evaluate("TW-02", tw, tmp_path / "tw-out", "local"), report_schema)
