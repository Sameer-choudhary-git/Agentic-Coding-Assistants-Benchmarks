"""Task-suite discovery, integrity and workspace handling."""

from __future__ import annotations

import json
import os
from collections import Counter

import pytest

from evaluator.paths import CATEGORIES, TASKS_ROOT
from evaluator.tasks import discover_tasks, get_task, iter_files
from evaluator.workspace import WorkspaceError, create_workspace, diff_snapshots, prepare_eval_dir, snapshot


def test_eighteen_tasks_three_per_category():
    tasks = discover_tasks()
    assert len(tasks) == 18
    counts = Counter(t.meta["category"] for t in tasks)
    assert counts == {c: 3 for c in CATEGORIES}
    assert len({t.id for t in tasks}) == 18


def test_every_task_has_required_assets():
    for task in discover_tasks():
        assert task.prompt().strip(), task.id
        assert any(iter_files(task.starter_dir)), task.id
        assert any(iter_files(task.reference_dir)), task.id
        if task.kind == "test_writing":
            manifest = json.loads((task.grading_dir / "mutants" / "manifest.json").read_text())
            assert len(manifest["mutants"]) >= 8
        else:
            assert list((task.grading_dir / "acceptance").glob("test_*.py")), task.id


def test_task_versions_and_hashes_are_stable():
    task = get_task("BF-01")
    first, second = task.hashes(), task.hashes()
    assert first == second
    assert len(first["task_hash"]) == 64
    assert task.meta["version"] and task.meta["test_version"]


def test_public_summary_does_not_leak_hidden_material():
    for task in discover_tasks():
        summary = json.dumps(task.public_summary())
        for path in iter_files(task.grading_dir):
            if path.suffix == ".py":
                body = path.read_text(encoding="utf-8")
                # A distinctive line from every hidden test file must not appear in the public summary.
                distinctive = max(body.splitlines(), key=len)
                assert distinctive not in summary, (task.id, path.name)
        for path in iter_files(task.reference_dir):
            ref_body = path.read_text(encoding="utf-8")
            longest = max(ref_body.splitlines(), key=len)
            assert longest not in summary or longest in task.prompt(), (task.id, path.name)
        assert "reference_hash" not in task.public_summary()


def test_all_tasks_validated_against_current_content():
    statuses = {t.id: t.validation_status()["status"] for t in discover_tasks()}
    assert set(statuses.values()) == {"validated"}, statuses


def test_create_workspace_copies_only_starter(tmp_path):
    task = get_task("RR-02")
    ws = create_workspace(task, tmp_path / "ws")
    files = sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*") if p.is_file())
    starter = sorted(p.relative_to(task.starter_dir).as_posix() for p in iter_files(task.starter_dir))
    assert files == starter
    assert not any("grading" in f or "reference" in f for f in files)
    with pytest.raises(WorkspaceError):
        create_workspace(task, ws)


def test_snapshot_ignores_tool_directories(tmp_path):
    task = get_task("BF-01")
    ws = create_workspace(task, tmp_path / "ws")
    (ws / ".git").mkdir()
    (ws / ".git" / "HEAD").write_text("ref")
    (ws / ".claude").mkdir()
    (ws / ".claude" / "settings.json").write_text("{}")
    (ws / "pager" / "__pycache__").mkdir()
    (ws / "pager" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    snap = snapshot(ws)
    assert all(not rel.startswith((".git", ".claude")) and "__pycache__" not in rel for rel in snap.files)
    assert ".claude" in snap.ignored_dirs


def test_diff_detects_changes_and_scope(tmp_path):
    task = get_task("BF-01")
    ws = create_workspace(task, tmp_path / "ws")
    target = ws / "pager" / "paginate.py"
    target.write_text(target.read_text().replace("total_items // per_page", "-(-total_items // per_page)"))
    (ws / "tests" / "test_new.py").write_text("def test_x():\n    assert True\n")
    (ws / "notes.txt").write_text("out of scope\n")
    (ws / "tests" / "test_smoke.py").unlink()
    diff = diff_snapshots(snapshot(task.starter_dir), snapshot(ws), task)
    changes = {c["path"]: c["change"] for c in diff["changed_files"]}
    assert changes == {
        "notes.txt": "added",
        "pager/paginate.py": "modified",
        "tests/test_new.py": "added",
        "tests/test_smoke.py": "deleted",
    }
    assert diff["out_of_scope_files"] == ["notes.txt"]
    assert "-(-total_items // per_page)" in diff["patch"]


def test_crlf_only_changes_are_not_reported(tmp_path):
    task = get_task("BF-01")
    ws = create_workspace(task, tmp_path / "ws")
    target = ws / "pager" / "paginate.py"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    diff = diff_snapshots(snapshot(task.starter_dir), snapshot(ws), task)
    assert diff["changed_files"] == []


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinks_rejected(tmp_path):
    task = get_task("BF-01")
    ws = create_workspace(task, tmp_path / "ws")
    os.symlink(TASKS_ROOT, ws / "escape.py")
    with pytest.raises(WorkspaceError):
        snapshot(ws)


def test_oversized_file_rejected(tmp_path):
    task = get_task("BF-01")
    ws = create_workspace(task, tmp_path / "ws")
    (ws / "big.bin").write_bytes(b"0" * 1_000_001)
    with pytest.raises(WorkspaceError):
        snapshot(ws)


def test_missing_workspace_rejected(tmp_path):
    with pytest.raises(WorkspaceError):
        snapshot(tmp_path / "does-not-exist")


def test_eval_dir_removes_harness_files_and_restores_protected(tmp_path):
    task = get_task("TW-01")
    ws = create_workspace(task, tmp_path / "ws")
    (ws / "conftest.py").write_text("raise SystemExit")
    (ws / "sitecustomize.py").write_text("raise SystemExit")
    (ws / "textstats" / "stats.py").write_text("def tokenize(t):\n    return []\n")
    actions = prepare_eval_dir(task, snapshot(ws), snapshot(task.starter_dir), tmp_path / "eval")
    assert actions["removed_harness_files"] == ["conftest.py", "sitecustomize.py"]
    assert actions["restored_protected_files"] == ["textstats/stats.py"]
    restored = (tmp_path / "eval" / "textstats" / "stats.py").read_text()
    assert restored == (task.starter_dir / "textstats" / "stats.py").read_text()
    assert (tmp_path / "eval" / "_acb" / "grading" / "mutants" / "manifest.json").exists()
