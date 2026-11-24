"""SWE-bench Verified as a second benchmark inside the platform.

The custom 18-task suite stays as it is. SWE-bench tasks are real GitHub issues from the human-validated
SWE-bench Verified set (princeton-nlp/SWE-bench_Verified). They plug into the same workflow (task list,
workspace, timed human-operated run, evaluation, results), but two steps differ:

* **Workspace.** The task's real repository is cloned at the issue's base commit, and the issue text is
  written to ISSUE.md (kept out of the patch).
* **Scoring.** The workspace diff becomes a SWE-bench prediction and is scored by the *official* SWE-bench
  harness in Docker. A task counts as resolved only if every FAIL_TO_PASS test (the tests the real fix
  made pass) and every PASS_TO_PASS test (existing behaviour) passes. That is the harness's own rule and
  the same success rule the custom suite uses (acceptance tests and regression tests).

Which tasks: ``swebench_pilot/candidates.json`` (12 instances chosen from leaderboard difficulty tertiles)
lists them. Their issue text and base commit come from the dataset, which ``swebench_pilot/pilot.py select``
downloads into ``swebench_pilot/manifest.json`` (Hugging Face access needed, free). Until then the tasks
show as "dataset missing" and cannot be put into an experiment.

Golden tasks: ``golden/dataset/app_tasks.json`` (written by ``python -m agentbench export-app`` in ``golden/``)
adds the golden dataset's runnable tasks as a third benchmark, ``golden``: SWE-bench Verified, Multilingual and
Multimodal tasks (scored by the official ``swebench`` harness with each task's own dataset) and SWE-bench Pro tasks
(scored in the task's published Docker image with Pro's run scripts, see ``run_pro``). They carry their issue
text, so no download is needed. Their category is the golden domain (bug fixing, feature implementation,
refactoring, performance, security remediation, frontend/visual) and their difficulty is the golden set's
calibrated tier. ``core`` marks a domain-balanced subset. A task already in the pilot stays in the pilot and only
gains the golden labels.

No AI service is called here. Scoring needs ``pip install swebench`` and a running Docker engine.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from evaluator import EVALUATOR_VERSION, REPORT_SCHEMA_VERSION
from evaluator.patch_quality import assess_patch
from evaluator.paths import REPO_ROOT

DATASET = "princeton-nlp/SWE-bench_Verified"
BENCHMARK = "swebench_verified"
CATEGORY = "swebench_verified"
GOLDEN_BENCHMARK = "golden"
# golden domain -> platform category (custom-suite names where one exists)
GOLDEN_CATEGORY = {
    "bug_fix": "bug_fixing",
    "feature_implementation": "feature_implementation",
    "refactoring": "refactoring",
    "security_fix": "security_remediation",
    "performance": "performance",
    "frontend_visual": "frontend_visual",
}
ISSUE_FILE = "ISSUE.md"
TIME_LIMIT_MINUTES = 30

PROMPT_TEMPLATE = """You are working in a checkout of the {repo} repository at commit {base_short}.

Resolve the GitHub issue below by changing the repository's source code. Do not modify or add tests unless
the issue explicitly asks for it; hidden tests will be run afterwards. Do not commit; leave your changes in
the working tree. Work offline: do not search the web or look up how the issue was fixed upstream. The issue
text is also saved in ISSUE.md in the repository root.

<issue>
{problem_statement}
</issue>
"""


class SwebenchError(Exception):
    pass


def _pilot_dir() -> Path:
    return Path(os.environ.get("ACB_SWEBENCH_DIR", REPO_ROOT / "swebench_pilot"))


def _golden_file() -> Path:
    return Path(os.environ.get("ACB_GOLDEN_APP_FILE", REPO_ROOT / "golden" / "dataset" / "app_tasks.json"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_instances() -> List[Dict[str, Any]]:
    """Candidates merged with the dataset manifest (when it has been downloaded)."""
    d = _pilot_dir()
    cand_path, man_path = d / "candidates.json", d / "manifest.json"
    candidates = json.loads(cand_path.read_text(encoding="utf-8"))["instances"] if cand_path.exists() else []
    manifest: Dict[str, Dict[str, Any]] = {}
    if man_path.exists():
        for e in json.loads(man_path.read_text(encoding="utf-8"))["instances"]:
            if _sha(e["problem_statement"]) != e["problem_statement_sha256"]:
                raise SwebenchError(f"manifest entry {e['instance_id']} was edited (problem statement hash mismatch)")
            manifest[e["instance_id"]] = e
    order = [c["instance_id"] for c in candidates] + [i for i in manifest if i not in {c["instance_id"] for c in candidates}]
    by_cand = {c["instance_id"]: c for c in candidates}
    out = [{**by_cand.get(i, {}), **manifest.get(i, {}), "instance_id": i, "_has_dataset": i in manifest} for i in order]
    golden = _load_golden()
    pilot_ids = set(order)
    for inst in out:  # pilot tasks that are also golden keep their benchmark and gain the golden labels
        g = golden.get(inst["instance_id"])
        if g:
            inst["golden"] = _golden_labels(g)
    out += [
        {**g, "golden": _golden_labels(g), "benchmark": GOLDEN_BENCHMARK, "_has_dataset": True}
        for i, g in golden.items()
        if i not in pilot_ids
    ]
    return out


def _golden_labels(g: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("golden_task_id", "source", "language", "core", "domain", "subdomain", "domain_confidence", "tier",
            "gold_quality_score", "gold_changed_source_lines", "gate_flags")
    return {k: g.get(k) for k in keys}


def _load_golden() -> Dict[str, Dict[str, Any]]:
    path = _golden_file()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    for e in data["instances"]:
        if _sha(e["problem_statement"]) != e["problem_statement_sha256"]:
            raise SwebenchError(f"golden entry {e['instance_id']} was edited (problem statement hash mismatch)")
        out[e["instance_id"]] = e
    return out


def is_swebench_id(task_id: str) -> bool:
    return "__" in task_id and any(i["instance_id"] == task_id for i in load_instances())


def get_instance(task_id: str) -> Dict[str, Any]:
    for i in load_instances():
        if i["instance_id"] == task_id:
            return i
    raise SwebenchError(f"unknown SWE-bench task: {task_id}")


def repo_of(instance_id: str) -> str:
    owner, rest = instance_id.split("__", 1)
    return f"{owner}/{rest.rsplit('-', 1)[0]}"


def prompt_for(inst: Dict[str, Any]) -> str:
    if not inst["_has_dataset"]:
        return (
            "Issue text not available yet. Download the SWE-bench Verified dataset with:\n"
            "  python swebench_pilot/pilot.py select --ids-from swebench_pilot/candidates.json\n"
            "then synchronise tasks."
        )
    return PROMPT_TEMPLATE.format(
        repo=inst["repo"], base_short=inst["base_commit"][:12], problem_statement=inst["problem_statement"].strip()
    )


def dataset_of(inst: Dict[str, Any]) -> str:
    return (inst.get("harness") or {}).get("dataset") or DATASET


def harness_type(inst: Dict[str, Any]) -> str:
    return (inst.get("harness") or {}).get("type") or "swebench"


def task_hashes(inst: Dict[str, Any]) -> Dict[str, str]:
    prompt = prompt_for(inst)
    base = inst.get("base_commit") or "unknown"
    prompt_hash = _sha(prompt)
    starter_hash = _sha(f"{inst.get('repo') or repo_of(inst['instance_id'])}@{base}")
    test_hash = _sha(f"{dataset_of(inst)}|{inst['instance_id']}|{inst.get('fail_to_pass_count')}|{inst.get('pass_to_pass_count')}")
    return {
        "task_hash": _sha(f"{inst['instance_id']}|{prompt_hash}|{starter_hash}|{test_hash}"),
        "prompt_hash": prompt_hash,
        "starter_hash": starter_hash,
        "test_hash": test_hash,
    }


def public_summary(inst: Dict[str, Any]) -> Dict[str, Any]:
    iid = inst["instance_id"]
    repo = inst.get("repo") or repo_of(iid)
    tier = inst.get("tier") or "medium"
    share = inst.get("share")
    benchmark = inst.get("benchmark", BENCHMARK)
    golden = inst.get("golden")
    is_golden = benchmark == GOLDEN_BENCHMARK
    number = iid.rsplit("-", 1)[1]
    first_line = ""
    if inst["_has_dataset"]:
        first_line = next((ln.strip() for ln in inst["problem_statement"].splitlines() if ln.strip()), "")[:160]
    rationale = (
        f"Resolved by {share:.0%} of SWE-bench Verified leaderboard submissions ({inst.get('solved_by')} of 122); "
        f"empirical-difficulty tertile: {tier}."
        if isinstance(share, (int, float))
        else f"Empirical-difficulty tertile: {tier}."
    )
    if is_golden:
        rationale = f"Golden-set calibrated tier: {tier} (patch complexity, thresholds fitted to SWE-bench annotators' labels)."
    if inst.get("difficulty"):
        rationale += f" Dataset annotators' time estimate: {inst['difficulty']}."
    return {
        "id": iid,
        "title": f"{repo} #{number}" if number.isdigit() else f"{repo} ({number})",  # Pro ids end in a commit hash
        "category": GOLDEN_CATEGORY.get(golden["domain"], golden["domain"]) if is_golden else CATEGORY,
        "benchmark": benchmark,
        "difficulty": tier,
        "difficulty_rationale": rationale,
        "version": "verified",
        "test_version": dataset_of(inst).split("/")[1],
        "kind": "swebench",
        "summary": first_line or "Real GitHub issue; text appears once the dataset is downloaded.",
        "required_behavior": [
            "Resolve the GitHub issue by changing the repository's source code.",
            "Keep existing behaviour working; the repository's other tests must still pass.",
        ],
        "acceptance_criteria": [
            "Scored in the task's SWE-bench Pro Docker image with Pro's test scripts."
            if harness_type(inst) == "swebench_pro"
            else "Scored by the official SWE-bench harness in Docker.",
            "Resolved only if every FAIL_TO_PASS test (made to pass by the real fix) passes and every PASS_TO_PASS test still passes.",
        ],
        "acceptance_tests": [],
        "scope": {"allowed_paths": ["any file in the repository"], "protected_paths": []},
        "time_limit_minutes": TIME_LIMIT_MINUTES,
        "test_timeout_seconds": int(os.environ.get("ACB_SWEBENCH_TIMEOUT_SECONDS", "1800")),
        "directory": f"swebench/{iid}",
        "starter_location": f"{repo} @ {(inst.get('base_commit') or 'base commit from dataset')[:12]}",
        "starter_files": [],
        "prompt": prompt_for(inst),
        **task_hashes(inst),
        "validation": {
            "status": "validated" if inst["_has_dataset"] else "dataset_missing",
            "validated_at": None,
            "expected_acceptance_total": inst.get("fail_to_pass_count"),
        },
        "swebench": {
            "dataset": dataset_of(inst),
            "harness": harness_type(inst),
            "repo": repo,
            "base_commit": inst.get("base_commit"),
            "tier": tier,
            "leaderboard_share": share,
            "leaderboard_solved_by": inst.get("solved_by"),
            "dataset_difficulty": inst.get("difficulty"),
            "fail_to_pass_count": inst.get("fail_to_pass_count"),
            "pass_to_pass_count": inst.get("pass_to_pass_count"),
            "has_dataset": inst["_has_dataset"],
            "golden": golden,
        },
    }


def list_summaries() -> List[Dict[str, Any]]:
    return [public_summary(i) for i in load_instances()]


# ------------------------------------------------------------------------------------------ git
def _git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    r = subprocess.run(["git", "-c", "core.autocrlf=false", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise SwebenchError(f"git {' '.join(args[:2])} failed: {r.stderr.strip()[-500:]}")
    return r.stdout


def create_workspace(task_id: str, destination: Path) -> Path:
    inst = get_instance(task_id)
    if not inst["_has_dataset"]:
        raise SwebenchError("SWE-bench dataset not downloaded yet; run swebench_pilot/pilot.py select first")
    if destination.exists() and any(destination.iterdir()):
        raise SwebenchError(f"workspace directory is not empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = os.environ.get("ACB_SWEBENCH_CLONE_URL", "https://github.com/{repo}.git").format(repo=inst["repo"])
    _git("clone", "--quiet", url, str(destination))
    _git("checkout", "--quiet", inst["base_commit"], cwd=destination)
    exclude = destination / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as f:
        f.write(f"\n{ISSUE_FILE}\n")
    (destination / ISSUE_FILE).write_text(prompt_for(inst), encoding="utf-8")
    return destination


def workspace_patch(workspace: Path, base_commit: str) -> str:
    """All changes (tracked and new files) relative to the base commit; the working tree is untouched."""
    _git("add", "-A", cwd=workspace)
    try:
        return _git("diff", "--cached", "--binary", base_commit, cwd=workspace)
    finally:
        _git("reset", "--quiet", cwd=workspace, check=False)


def diff_stats(patch: str) -> Dict[str, Any]:
    files = re.findall(r"^diff --git a/(\S+) b/", patch, flags=re.M)
    added = sum(1 for ln in patch.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in patch.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    test_files = [f for f in files if re.search(r"(^|/)tests?(/|_)|_test\.py$|(^|/)test_[^/]*\.py$", f)]
    return {"files_changed": len(files), "lines_added": added, "lines_removed": removed, "files": files,
            "test_files_changed": test_files, "out_of_scope_files": []}  # fmt: skip


# ------------------------------------------------------------------------------------- harness
def harness_dataset() -> str:
    """Dataset name for the installed harness.

    swebench 5.x needs the SWE-bench/* datasets, which carry each task's Docker image and evaluation
    script; older versions use princeton-nlp/SWE-bench_Verified. Both hold the same 500 Verified tasks.
    Override with ACB_SWEBENCH_HARNESS_DATASET (e.g. a local .jsonl or .parquet file).
    """
    override = os.environ.get("ACB_SWEBENCH_HARNESS_DATASET")
    if override:
        return override
    try:
        from importlib.metadata import version

        major = int(version("swebench").split(".")[0])
    except Exception:  # noqa: BLE001 - not installed or unparsable version
        major = 4
    return "SWE-bench/SWE-bench_Verified" if major >= 5 else DATASET


def harness_command(
    preds: Path, instance_id: str, run_id: str, timeout_s: int, dataset: Optional[str] = None, split: str = "test"
) -> List[str]:
    override = os.environ.get("ACB_SWEBENCH_HARNESS")
    if override:  # used by tests and for custom setups (e.g. a remote runner)
        return shlex.split(override) + [str(preds), instance_id, run_id]
    # Verified keeps the version-dependent name; Multilingual/Multimodal are only published as SWE-bench/*
    name = harness_dataset() if not dataset or dataset == DATASET else dataset
    return [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", name,
        "--split", split,
        "--predictions_path", str(preds),
        "--instance_ids", instance_id,
        "--max_workers", "1",
        "--run_id", run_id,
        "--timeout", str(timeout_s),
    ]  # fmt: skip


# ----------------------------------------------------------------------------------- SWE-bench Pro
PRO_SCRIPTS_HINT = (
    "SWE-bench Pro tasks need Pro's per-task test scripts: git clone https://github.com/scaleapi/SWE-bench_Pro-os "
    "and set ACB_SWEBENCH_PRO_SCRIPTS to its run_scripts folder."
)


def _docker_cmd() -> List[str]:
    """``docker`` unless ACB_DOCKER overrides it (tests use a stand-in)."""
    return shlex.split(os.environ.get("ACB_DOCKER", "docker"))


def pro_scripts_dir(inst: Dict[str, Any]) -> Optional[Path]:
    root = os.environ.get("ACB_SWEBENCH_PRO_SCRIPTS")
    if not root:
        return None
    d = Path(root) / (inst.get("source_instance_id") or inst["instance_id"])
    return d if (d / "run_script.sh").exists() and (d / "parser.py").exists() else None


PRO_ENTRY = """set +e
cd /app
git reset --hard {base}
git checkout {base}
git apply -v /workspace/patch.diff > /workspace/apply.log 2>&1
echo $? > /workspace/apply_status
if [ "$(cat /workspace/apply_status)" != "0" ]; then exit 0; fi
mkdir -p /tests
cp /workspace/test_patch.patch /tests/test_patch.patch
{test_setup}
bash /workspace/run_script.sh {tests} > /workspace/stdout.log 2> /workspace/stderr.log
python /workspace/parser.py /workspace/stdout.log /workspace/stderr.log /workspace/output.json
"""


def run_pro(inst: Dict[str, Any], patch: str, out_dir: Path, timeout_s: int) -> Dict[str, Any]:
    """Score a patch the way SWE-bench Pro's evaluator does: in the task's image, reset to the base commit,
    apply the patch, apply the hidden test patch (last line of before_repo_set_cmd), run the task's run script
    on the selected test files and parse the output. Resolved when every FAIL_TO_PASS and PASS_TO_PASS test passes.
    Returns a dict in the official harness's report format."""
    h = inst["harness"]
    scripts = pro_scripts_dir(inst)
    if scripts is None and not os.environ.get("ACB_DOCKER"):
        raise SwebenchError(PRO_SCRIPTS_HINT)
    work = out_dir / "pro"
    work.mkdir(parents=True, exist_ok=True)
    for name in ("run_script.sh", "parser.py"):
        src = scripts / name if scripts else None
        (work / name).write_text(src.read_text(encoding="utf-8") if src else "", encoding="utf-8", newline="\n")
    (work / "patch.diff").write_text(patch, encoding="utf-8", newline="\n")
    (work / "test_patch.patch").write_text(h.get("test_patch") or "", encoding="utf-8", newline="\n")
    setup = [ln for ln in (h.get("before_repo_set_cmd") or "").strip().splitlines() if ln.strip()]
    entry = PRO_ENTRY.format(
        base=inst["base_commit"], test_setup=setup[-1] if setup else "", tests=",".join(h.get("selected_test_files_to_run") or [])
    )
    (work / "entry.sh").write_text(entry, encoding="utf-8", newline="\n")
    cmd = _docker_cmd() + [
        "run", "--rm", "--platform", "linux/amd64", "-v", f"{work.resolve()}:/workspace",
        "--entrypoint", "/bin/bash", h["docker_image"], "/workspace/entry.sh",
    ]  # fmt: skip
    proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout_s + 3600)  # fmt: skip
    (out_dir / "harness.log").write_text((proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""), encoding="utf-8")
    status_file = work / "apply_status"
    if not status_file.exists():
        err = (proc.stderr or proc.stdout or "no output").strip().splitlines() or ["no output"]
        raise SwebenchError(f"Pro container exited {proc.returncode} without running the tests. Last line: {err[-1][:400]}")
    applied = status_file.read_text(encoding="utf-8").strip() == "0"
    passed: set = set()
    out_json = work / "output.json"
    if applied and out_json.exists():
        tests = json.loads(out_json.read_text(encoding="utf-8")).get("tests", [])
        passed = {t["name"] for t in tests if str(t.get("status", "")).upper() == "PASSED"}
    f2p, p2p = h.get("fail_to_pass") or [], h.get("pass_to_pass") or []

    def split(names: List[str]) -> Dict[str, List[str]]:
        return {"success": [n for n in names if n in passed], "failure": [n for n in names if n not in passed]}

    status = {"FAIL_TO_PASS": split(f2p), "PASS_TO_PASS": split(p2p)}
    resolved = applied and bool(f2p) and not status["FAIL_TO_PASS"]["failure"] and not status["PASS_TO_PASS"]["failure"]
    return {"patch_successfully_applied": applied, "resolved": resolved, "tests_status": status}


def harness_available(inst: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """None when scoring can run, else the reason it cannot."""
    if inst is not None and harness_type(inst) == "swebench_pro":
        if os.environ.get("ACB_DOCKER"):
            return None
        if pro_scripts_dir(inst) is None:
            return PRO_SCRIPTS_HINT
    elif os.environ.get("ACB_SWEBENCH_HARNESS"):
        return None
    else:
        try:
            import swebench  # noqa: F401
        except ImportError:
            return "the swebench package is not installed (pip install swebench)"
    if not shutil.which("docker"):
        return "Docker is not installed or not on PATH" + _docker_hint()
    try:
        probe = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        probe = None
    if probe is None or probe.returncode != 0:
        lines = ((probe.stderr or probe.stdout).strip().splitlines() if probe else []) or ["no response"]
        return f"The Docker engine is not reachable ({lines[-1][:200]})." + _docker_hint()
    return None


def _docker_hint() -> str:
    if os.environ.get("WSL_DISTRO_NAME"):
        return (
            " In WSL: start Docker Desktop, open Settings > Resources > WSL integration, turn on your Ubuntu "
            "distribution, click Apply & restart, then check that `docker info` works in Ubuntu."
        )
    return " Start Docker Desktop (or the Docker service) and check that `docker info` works."


def _suite(status: Dict[str, Any]) -> Dict[str, Any]:
    ok, bad = list(status.get("success", [])), list(status.get("failure", []))
    tests = [{"id": t, "outcome": "passed"} for t in ok] + [{"id": t, "outcome": "failed"} for t in bad]
    return {"status": "ran" if tests else "none", "passed": len(ok), "failed": len(bad), "errors": 0, "total": len(tests),
            "expected_total": len(tests), "tests": tests}  # fmt: skip


def evaluate(
    task_id: str,
    workspace: Path,
    out_dir: Path,
    expected_task_hash: Optional[str] = None,
    run_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started, t0 = datetime.now(timezone.utc), time.monotonic()
    out_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "benchmark": BENCHMARK,
        "status": "error",
        "success": None,
        "outcome": "evaluator_error",
        "error": None,
        "started_at": started.isoformat(),
        "duration_s": None,
        "task": {"id": task_id, "kind": "swebench", "dataset": DATASET},  # dataset updated per task below
        "run_context": run_context or {},
        "workspace": {"name": workspace.name},
        "diff": None,
        "acceptance": None,
        "regression": None,
        "test_quality": None,
        "ruff": {"status": "not_applicable"},
        "semgrep": {"status": "not_applicable"},
        "code_quality": {"status": "not_applicable"},
        "environment": {"host_python": sys.version.split()[0], "execution": "swebench-harness (docker)"},
        "swebench": None,
    }

    def finish() -> Dict[str, Any]:
        report["duration_s"] = round(time.monotonic() - t0, 2)
        (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    try:
        inst = get_instance(task_id)
        if not inst["_has_dataset"]:
            raise SwebenchError("SWE-bench dataset not downloaded; run swebench_pilot/pilot.py select first")
        report["benchmark"] = inst.get("benchmark", BENCHMARK)
        report["task"]["dataset"] = dataset_of(inst)
        pro = harness_type(inst) == "swebench_pro"
        if pro:
            report["environment"]["execution"] = "swebench-pro image (docker)"
        hashes = task_hashes(inst)
        report["task"].update(hashes)
        if expected_task_hash and expected_task_hash != hashes["task_hash"]:
            report["error"] = {"class": "task_changed", "message": "task hash differs from the one recorded for this run"}
            return finish()
        if not (workspace / ".git").exists():
            raise SwebenchError(f"workspace is not a git checkout: {workspace}")
        patch = workspace_patch(workspace, inst["base_commit"])
        (out_dir / "patch.diff").write_text(patch, encoding="utf-8")
        report["workspace"]["snapshot_hash"] = _sha(patch)
        report["diff"] = diff_stats(patch)
        if not patch.strip():
            report.update(status="completed", success=False, outcome="empty_patch")
            report["swebench"] = {"resolved": False, "patch_applied": None, "harness_run": False}
            return finish()
        # static, host-side and read-only: scored even when Docker is missing, so quality is never lost to setup
        labels = inst.get("golden") or {}
        report["code_quality"] = assess_patch(
            workspace, inst["base_commit"], patch, inst.get("repo") or "",
            reference_lines=labels.get("gold_changed_source_lines"), gold_quality_score=labels.get("gold_quality_score"),
        )  # fmt: skip
        reason = harness_available(inst)
        if reason:
            report["error"] = {"class": "harness_unavailable", "message": reason}
            return finish()
        model = str((run_context or {}).get("assistant_id") or "acb")
        run_id = f"acb-{(run_context or {}).get('run_id') or int(time.time())}"
        timeout_s = int(os.environ.get("ACB_SWEBENCH_TIMEOUT_SECONDS", "1800"))
        harness_report = None
        if pro:
            per = run_pro(inst, patch, out_dir, timeout_s)
            (out_dir / "pro_report.json").write_text(json.dumps(per, indent=2), encoding="utf-8")
            harness_report = "pro_report.json"
        else:
            # the harness looks tasks up by their dataset id, which can differ from the app id
            hid = inst.get("source_instance_id") or task_id
            preds = out_dir / "predictions.jsonl"
            preds.write_text(json.dumps({"instance_id": hid, "model_name_or_path": model, "model_patch": patch}) + "\n", encoding="utf-8")
            h = inst.get("harness") or {}
            proc = subprocess.run(
                harness_command(preds, hid, run_id, timeout_s, h.get("dataset"), h.get("split") or "test"), cwd=out_dir,
                capture_output=True, text=True, encoding="utf-8", timeout=timeout_s + 3600,  # first image builds are slow
            )  # fmt: skip
            (out_dir / "harness.log").write_text((proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""), encoding="utf-8")
            found = list((out_dir / "logs" / "run_evaluation" / run_id).glob(f"*/{hid}/report.json"))
            if not found:
                err = proc.stderr or proc.stdout or ""
                lines = err.strip().splitlines() or ["no output"]
                msg = f"harness exited {proc.returncode} without a report. Last line: {lines[-1][:400]} (full log: harness.log)."
                if "DockerException" in err or "docker.sock" in err:
                    msg += " The harness could not reach Docker." + _docker_hint()
                report["error"] = {"class": "harness_error", "message": msg}
                return finish()
            per = json.loads(found[0].read_text(encoding="utf-8"))[hid]
            harness_report = str(found[0].relative_to(out_dir))
        tests = per.get("tests_status") or {}
        report["acceptance"] = _suite(tests.get("FAIL_TO_PASS", {}))
        report["regression"] = _suite(tests.get("PASS_TO_PASS", {}))
        applied = bool(per.get("patch_successfully_applied"))
        resolved = bool(per.get("resolved"))
        report["swebench"] = {"resolved": resolved, "patch_applied": applied, "harness_run": True, "harness_run_id": run_id,
                              "harness": harness_type(inst), "harness_report": harness_report}  # fmt: skip
        if not applied:
            outcome = "patch_failed"
        elif resolved:
            outcome = "passed"
        elif report["acceptance"]["failed"]:
            outcome = "acceptance_failed"
        else:
            outcome = "regression_failed"
        report.update(status="completed", success=resolved, outcome=outcome)
        return finish()
    except subprocess.TimeoutExpired:
        report["error"] = {"class": "harness_timeout", "message": "the SWE-bench harness did not finish in time"}
        return finish()
    except (SwebenchError, OSError, KeyError, json.JSONDecodeError) as exc:
        report["error"] = {"class": type(exc).__name__, "message": str(exc)[:2000]}
        return finish()
