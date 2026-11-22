"""SWE-bench Verified integration: task listing, workspace from a real git checkout, and scoring through a
stand-in for the official harness that writes a report in the harness's own format."""

import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from evaluator import cli, swebench

IID = "acme__widgets-42"


@pytest.fixture(autouse=True)
def no_real_golden(tmp_path, monkeypatch):
    """Keep the repo's golden task file out of these tests; the golden test points at its own file."""
    monkeypatch.setenv("ACB_GOLDEN_APP_FILE", str(tmp_path / "no-golden.json"))


def git(cwd, *args):
    cmd = ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args]
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def upstream(tmp_path):
    repo = tmp_path / "upstream"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "widgets.py").write_text("def area(w, h):\n    return w + h\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    return repo, git(repo, "rev-parse", "HEAD").strip()


def write_pilot(tmp_path, base=None, with_manifest=True):
    d = tmp_path / "pilot"
    d.mkdir(exist_ok=True)
    cand = {"instances": [{"instance_id": IID, "repo": "acme/widgets", "tier": "hard", "share": 0.25, "solved_by": 30}]}
    (d / "candidates.json").write_text(json.dumps(cand))
    if with_manifest:
        ps = "area() adds instead of multiplying."
        entry = {
            "instance_id": IID,
            "repo": "acme/widgets",
            "base_commit": base,
            "difficulty": "<15 min fix",
            "tier": "hard",
            "fail_to_pass_count": 1,
            "pass_to_pass_count": 1,
            "problem_statement": ps,
            "problem_statement_sha256": hashlib.sha256(ps.encode()).hexdigest(),
        }
        (d / "manifest.json").write_text(json.dumps({"instances": [entry]}))
    return d


FAKE_HARNESS = textwrap.dedent(
    """
    import json, pathlib, sys
    preds, iid, run_id = sys.argv[1], sys.argv[2], sys.argv[3]
    patch = json.loads(open(preds).read())["model_patch"]
    fixed = "w * h" in patch
    out = pathlib.Path("logs/run_evaluation") / run_id / "codex" / iid
    out.mkdir(parents=True)
    status = {
        "FAIL_TO_PASS": {"success": ["test_area"] if fixed else [], "failure": [] if fixed else ["test_area"]},
        "PASS_TO_PASS": {"success": ["test_import"], "failure": []},
    }
    report = {iid: {"patch_is_None": False, "patch_exists": True, "patch_successfully_applied": True,
                    "resolved": fixed, "tests_status": status}}
    (out / "report.json").write_text(json.dumps(report))
    """
)


def test_tasks_without_dataset_are_listed_but_not_ready(tmp_path, monkeypatch):
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(write_pilot(tmp_path, with_manifest=False)))
    [s] = swebench.list_summaries()
    assert s["id"] == IID and s["benchmark"] == "swebench_verified" and s["category"] == "swebench_verified"
    assert s["validation"]["status"] == "dataset_missing"
    assert "pilot.py select" in s["prompt"]
    assert s["difficulty"] == "hard" and "25%" in s["difficulty_rationale"]
    with pytest.raises(swebench.SwebenchError, match="not downloaded"):
        swebench.create_workspace(IID, tmp_path / "ws")


def test_manifest_makes_task_ready_and_detects_edits(tmp_path, monkeypatch, upstream):
    d = write_pilot(tmp_path, base=upstream[1])
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(d))
    [s] = swebench.list_summaries()
    assert s["validation"]["status"] == "validated"
    assert s["validation"]["expected_acceptance_total"] == 1
    assert "area() adds instead of multiplying." in s["prompt"] and "acme/widgets" in s["prompt"]
    assert s["swebench"]["base_commit"] == upstream[1]
    data = json.loads((d / "manifest.json").read_text())
    data["instances"][0]["problem_statement"] = "edited"
    (d / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(swebench.SwebenchError, match="hash mismatch"):
        swebench.list_summaries()


def test_cli_lists_both_benchmarks(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(write_pilot(tmp_path, with_manifest=False)))
    assert cli.main(["list-tasks", "--json", "--compact"]) == 0
    tasks = json.loads(capsys.readouterr().out)
    benches = {t["benchmark"] for t in tasks}
    assert benches == {"custom", "swebench_verified"}
    assert sum(t["benchmark"] == "custom" for t in tasks) == 18


@pytest.fixture
def ready(tmp_path, monkeypatch, upstream):
    repo, base = upstream
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(write_pilot(tmp_path, base=base)))
    monkeypatch.setenv("ACB_SWEBENCH_CLONE_URL", str(repo))
    harness = tmp_path / "fake_harness.py"
    harness.write_text(FAKE_HARNESS)
    monkeypatch.setenv("ACB_SWEBENCH_HARNESS", f'"{sys.executable}" "{harness}"')
    ws = swebench.create_workspace(IID, tmp_path / "ws")
    return ws, tmp_path


def test_workspace_is_checkout_at_base_with_issue_file(ready):
    ws, _ = ready
    assert (ws / "widgets.py").exists()
    assert "multiplying" in (ws / "ISSUE.md").read_text()
    assert git(ws, "status", "--porcelain") == ""  # ISSUE.md is excluded from the patch
    with pytest.raises(swebench.SwebenchError, match="not empty"):
        swebench.create_workspace(IID, ws)


def test_resolved_patch_scores_as_passed(ready):
    ws, tmp = ready
    (ws / "widgets.py").write_text("def area(w, h):\n    return w * h\n")
    (ws / "notes_new.py").write_text("X = 1\n")
    rep = swebench.evaluate(IID, ws, tmp / "out", run_context={"run_id": "r1", "assistant_id": "codex"})
    assert rep["status"] == "completed" and rep["success"] is True and rep["outcome"] == "passed"
    assert rep["acceptance"]["passed"] == 1 and rep["regression"]["passed"] == 1
    assert rep["diff"]["files_changed"] == 2 and "ISSUE.md" not in (tmp / "out" / "patch.diff").read_text()
    assert json.loads((tmp / "out" / "report.json").read_text())["swebench"]["resolved"] is True
    assert git(ws, "diff", "--cached") == ""  # the operator's index is left as it was


def test_unresolved_patch_and_empty_patch(ready):
    ws, tmp = ready
    rep = swebench.evaluate(IID, ws, tmp / "empty")
    assert rep["status"] == "completed" and rep["outcome"] == "empty_patch" and rep["success"] is False
    (ws / "widgets.py").write_text("def area(w, h):\n    return w - h\n")
    rep = swebench.evaluate(IID, ws, tmp / "wrong", run_context={"run_id": "r2", "assistant_id": "codex"})
    assert rep["success"] is False and rep["outcome"] == "acceptance_failed"
    assert rep["acceptance"]["failed"] == 1


def test_task_hash_mismatch_and_missing_harness(ready, monkeypatch):
    ws, tmp = ready
    (ws / "widgets.py").write_text("def area(w, h):\n    return w * h\n")
    rep = swebench.evaluate(IID, ws, tmp / "h", expected_task_hash="0" * 64)
    assert rep["status"] == "error" and rep["error"]["class"] == "task_changed"
    monkeypatch.delenv("ACB_SWEBENCH_HARNESS")
    monkeypatch.setattr(swebench, "harness_available", lambda inst=None: "Docker is not installed or not on PATH")
    rep = swebench.evaluate(IID, ws, tmp / "nh")
    assert rep["status"] == "error" and rep["error"]["class"] == "harness_unavailable"


def test_unreachable_docker_engine_is_reported_with_a_fix(monkeypatch):
    import types

    monkeypatch.delenv("ACB_SWEBENCH_HARNESS", raising=False)
    monkeypatch.setitem(sys.modules, "swebench", types.ModuleType("swebench"))
    monkeypatch.setattr(swebench.shutil, "which", lambda name: "/usr/bin/docker")
    failed = subprocess.CompletedProcess(["docker"], 1, stdout="", stderr="Cannot connect to the Docker daemon")
    monkeypatch.setattr(swebench.subprocess, "run", lambda *a, **k: failed)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    reason = swebench.harness_available()
    assert "not reachable" in reason and "Cannot connect" in reason and "WSL integration" in reason
    ok = subprocess.CompletedProcess(["docker"], 0, stdout="27.0.3", stderr="")
    monkeypatch.setattr(swebench.subprocess, "run", lambda *a, **k: ok)
    assert swebench.harness_available() is None


def test_harness_dataset_matches_installed_harness_version(monkeypatch):
    import importlib.metadata as md

    monkeypatch.delenv("ACB_SWEBENCH_HARNESS_DATASET", raising=False)
    monkeypatch.setattr(md, "version", lambda name: "5.0.2")
    assert swebench.harness_dataset() == "SWE-bench/SWE-bench_Verified"
    monkeypatch.setattr(md, "version", lambda name: "4.1.0")
    assert swebench.harness_dataset() == "princeton-nlp/SWE-bench_Verified"
    monkeypatch.setenv("ACB_SWEBENCH_HARNESS_DATASET", "/data/verified.jsonl")
    assert swebench.harness_dataset() == "/data/verified.jsonl"


def test_golden_tasks_become_third_benchmark(tmp_path, monkeypatch):
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(write_pilot(tmp_path, base="abc123")))

    def entry(iid, domain, tier):
        ps = f"{iid}: something is broken."
        return {"instance_id": iid, "golden_task_id": f"swebench_verified::{iid}", "repo": "acme/widgets",
                "base_commit": "abc123", "tier": tier, "domain": domain, "subdomain": None, "gold_quality_score": 97.0,
                "gate_flags": [], "fail_to_pass_count": 1, "pass_to_pass_count": 2,
                "problem_statement": ps, "problem_statement_sha256": hashlib.sha256(ps.encode()).hexdigest()}

    gf = tmp_path / "golden.json"
    gf.write_text(json.dumps({"instances": [entry(IID, "bug_fix", "easy"), entry("acme__widgets-7", "performance", "hard")]}))
    monkeypatch.setenv("ACB_GOLDEN_APP_FILE", str(gf))
    by_id = {s["id"]: s for s in swebench.list_summaries()}
    # the pilot keeps its own task and only gains the golden labels
    assert by_id[IID]["benchmark"] == "swebench_verified" and by_id[IID]["swebench"]["golden"]["domain"] == "bug_fix"
    g = by_id["acme__widgets-7"]
    assert g["benchmark"] == "golden" and g["category"] == "performance" and g["difficulty"] == "hard"
    assert g["validation"]["status"] == "validated" and "something is broken" in g["prompt"]
    assert swebench.is_swebench_id("acme__widgets-7")


FAKE_DOCKER = textwrap.dedent(
    """
    import json, pathlib, sys
    args = sys.argv[1:]
    work = pathlib.Path(args[args.index("-v") + 1].rsplit(":/workspace", 1)[0])
    entry = (work / "entry.sh").read_text()
    assert "git apply -v /workspace/patch.diff" in entry and "acme.test.js" in entry, entry
    assert args[-1] == "/workspace/entry.sh" and args[-2] == "img:tag"
    (work / "apply_status").write_text("0")
    fixed = "w * h" in (work / "patch.diff").read_text()
    tests = [{"name": "t | area multiplies", "status": "PASSED" if fixed else "FAILED"},
             {"name": "t | still works", "status": "PASSED"}]
    (work / "output.json").write_text(json.dumps({"tests": tests}))
    """
)


def test_pro_task_scored_in_its_image(tmp_path, monkeypatch, upstream):
    repo, base = upstream
    monkeypatch.setenv("ACB_SWEBENCH_DIR", str(write_pilot(tmp_path, with_manifest=False)))
    monkeypatch.setenv("ACB_SWEBENCH_CLONE_URL", str(repo))
    ps = "Area should multiply. ## Requirements\n- area(w, h) returns w * h"
    long_id = "instance_acme__widgets-" + "a" * 40 + "-v" + "b" * 40
    pro = {"instance_id": "acme__widgets-aaaaaaaaaa", "source_instance_id": long_id, "source": "swebench_pro",
           "repo": "acme/widgets", "base_commit": base, "tier": "medium", "domain": "refactoring", "core": True,
           "fail_to_pass_count": 1, "pass_to_pass_count": 1, "problem_statement": ps,
           "problem_statement_sha256": hashlib.sha256(ps.encode()).hexdigest(),
           "harness": {"type": "swebench_pro", "dataset": "ScaleAI/SWE-bench_Pro", "docker_image": "img:tag",
                       "before_repo_set_cmd": "git reset --hard x\ngit apply /tests/test_patch.patch",
                       "selected_test_files_to_run": ["acme.test.js"], "fail_to_pass": ["t | area multiplies"],
                       "pass_to_pass": ["t | still works"], "test_patch": "diff --git a/t b/t\n"}}
    gf = tmp_path / "golden.json"
    gf.write_text(json.dumps({"instances": [pro]}))
    monkeypatch.setenv("ACB_GOLDEN_APP_FILE", str(gf))
    fake = tmp_path / "fake_docker.py"
    fake.write_text(FAKE_DOCKER)
    monkeypatch.setenv("ACB_DOCKER", f'"{sys.executable}" "{fake}"')

    [s] = [x for x in swebench.list_summaries() if x["benchmark"] == "golden"]
    assert s["category"] == "refactoring" and s["swebench"]["harness"] == "swebench_pro"
    assert s["swebench"]["golden"]["core"] is True and "Pro Docker image" in s["acceptance_criteria"][0]

    ws = swebench.create_workspace(pro["instance_id"], tmp_path / "ws")
    rep = swebench.evaluate(pro["instance_id"], ws, tmp_path / "unresolved")
    assert rep["status"] == "completed" and rep["success"] is False and rep["outcome"] == "empty_patch"
    (ws / "widgets.py").write_text("def area(w, h):\n    return w * h\n")
    rep = swebench.evaluate(pro["instance_id"], ws, tmp_path / "out")
    assert rep["success"] is True and rep["outcome"] == "passed" and rep["benchmark"] == "golden"
    assert rep["task"]["dataset"] == "ScaleAI/SWE-bench_Pro" and rep["swebench"]["harness"] == "swebench_pro"
    assert rep["acceptance"]["passed"] == 1 and rep["regression"]["passed"] == 1
    (ws / "widgets.py").write_text("def area(w, h):\n    return w - h\n")
    rep = swebench.evaluate(pro["instance_id"], ws, tmp_path / "bad")
    assert rep["success"] is False and rep["outcome"] == "acceptance_failed"


def test_pro_task_without_scripts_explains_setup(monkeypatch):
    monkeypatch.delenv("ACB_DOCKER", raising=False)
    monkeypatch.delenv("ACB_SWEBENCH_PRO_SCRIPTS", raising=False)
    inst = {"instance_id": "x__y-1", "harness": {"type": "swebench_pro"}}
    assert "SWE-bench_Pro-os" in swebench.harness_available(inst)


def test_harness_command_uses_each_tasks_dataset(monkeypatch):
    monkeypatch.delenv("ACB_SWEBENCH_HARNESS", raising=False)
    cmd = swebench.harness_command(Path("p.jsonl"), "a__b-1", "r", 60, "SWE-bench/SWE-bench_Multimodal", "dev")
    assert cmd[cmd.index("--dataset_name") + 1] == "SWE-bench/SWE-bench_Multimodal"
    assert cmd[cmd.index("--split") + 1] == "dev"
