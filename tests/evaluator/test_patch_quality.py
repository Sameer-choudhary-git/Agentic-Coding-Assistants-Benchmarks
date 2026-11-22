"""Code quality of an assistant's patch (evaluator/patch_quality.py) on a throwaway git repository."""

import subprocess
from pathlib import Path

import pytest

from evaluator.patch_quality import assess_patch

pytest.importorskip("lizard")
pytest.importorskip("radon")

BASE = '''def total(items):
    """Sum of item prices."""
    return sum(i.price for i in items)
'''

CLEAN = '''def total(items):
    """Sum of item prices, ignoring missing ones."""
    return sum(i.price for i in items if i.price is not None)
'''

SLOPPY = '''import os


def total(items):
    """Sum of item prices."""
    print("debug", items)
    # TODO: handle None
    try:
        return eval("sum(i.price for i in items)")
    except:
        pass
'''


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _repo_with_change(tmp_path: Path, new_source: str, extra: dict | None = None) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    (repo / "shop").mkdir(parents=True)
    (repo / "shop" / "cart.py").write_text(BASE, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "shop" / "cart.py").write_text(new_source, encoding="utf-8")
    for rel, text in (extra or {}).items():
        (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    patch = _git(repo, "diff", "--cached", base)
    _git(repo, "reset", "-q")
    _git(repo, "checkout", "-q", "--", ".")
    _git(repo, "clean", "-qfd")
    return repo, base, patch


def test_clean_patch_has_no_penalties_and_compares_with_reference(tmp_path):
    repo, base, patch = _repo_with_change(tmp_path, CLEAN)
    q = assess_patch(repo, base, patch, "acme/shop", reference_lines=4, gold_quality_score=100.0)
    assert q["status"] == "ran"
    assert q["coverage"]["analyzed_files"] == 1, "the file must be read from git at the base commit"
    # nothing new to charge except radon's maintainability index, which swings on a 3-line file
    assert {k: v for k, v in q["penalties"].items() if k != "maintainability"} == dict.fromkeys(
        ("reliability", "complexity", "security", "hygiene", "size"), 0
    )
    assert q["quality_score"] >= 90
    assert q["size_ratio_vs_reference"] == 1.0
    assert q["delta_vs_gold"] == round(q["quality_score"] - 100.0, 1)


def test_sloppy_patch_is_penalised_for_each_new_problem(tmp_path):
    repo, base, patch = _repo_with_change(tmp_path, SLOPPY, extra={"reproduce_issue.py": "print('x')\n"})
    q = assess_patch(repo, base, patch, "acme/shop", reference_lines=2, gold_quality_score=100.0)
    assert q["status"] == "ran"
    assert q["quality_score"] < 70
    assert q["smells"].get("debug_statement") and q["smells"].get("todo_marker") and q["smells"].get("broad_exception")
    assert q["stray_files"] == ["reproduce_issue.py"]
    assert q["subscores"]["hygiene"] < 100 and q["subscores"]["security"] < 100
    assert q["delta_vs_gold"] < 0


def test_empty_patch_and_missing_tools_are_reported_not_scored(tmp_path, monkeypatch):
    assert assess_patch(tmp_path, "HEAD", "  \n")["status"] == "not_applicable"

    def missing():
        raise ImportError("No module named 'lizard'")

    monkeypatch.setattr("evaluator.patch_quality._assessor_class", missing)
    q = assess_patch(tmp_path, "HEAD", "diff --git a/x.py b/x.py\n")
    assert q["status"] == "unavailable" and "pip install" in q["error"]
