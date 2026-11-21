"""Execution adapters: run predictions against each task's upstream environment.

Execution requires Docker and the upstream harness packages; these adapters
build the exact command lines and parse their reports so a full run is one
command (``python -m agentbench evaluate --predictions p.jsonl --run-harness``).

  harness=swebench           -> `swebench` package (Verified, Multilingual, Multimodal, SWE-bench+)
  harness=swe_rebench        -> `swebench` package with SWE-rebench prebuilt images
  harness=swebench_pro       -> scaleapi/SWE-bench_Pro-os  (swe_bench_pro_eval.py)
  harness=swebench_plusplus  -> TuringEnterprises SWE-Bench++ runner
  harness=harbor             -> NYU CTF via Harbor; flag_match judge below
  eval_type=test_generation  -> two runs (base, base+gold) and the SWT-bench criterion below
"""
from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import subprocess
import sys
from collections import defaultdict

log = logging.getLogger(__name__)

SWEBENCH_DATASETS = {
    "swebench_verified": ("princeton-nlp/SWE-bench_Verified", "test"),
    "swebench_multilingual": ("SWE-bench/SWE-bench_Multilingual", "test"),
    "swebench_multimodal": ("SWE-bench/SWE-bench_Multimodal", "dev"),
    "swe_rebench": ("nebius/SWE-rebench", "filtered"),
}


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def swebench_command(source: str, preds_path: str, instance_ids: list[str], run_id: str,
                     workers: int = 4) -> list[str]:
    ds, split = SWEBENCH_DATASETS[source]
    return [sys.executable, "-m", "swebench.harness.run_evaluation", "--dataset_name", ds, "--split", split,
            "--predictions_path", preds_path, "--instance_ids", *instance_ids, "--run_id", run_id,
            "--max_workers", str(workers), "--cache_level", "env"]


def run_swebench(tasks: list[dict], preds: dict[str, dict], out_dir: str, run_id: str) -> dict[str, bool]:
    """Run the official SWE-bench docker harness per source; returns {task_id: resolved}."""
    if not docker_available():
        raise RuntimeError("Docker is not available: cannot execute tests. Use --results or published runs.")
    try:
        import swebench  # noqa: F401
    except ImportError as e:
        raise RuntimeError("pip install swebench  (official harness) is required for --run-harness") from e
    os.makedirs(out_dir, exist_ok=True)
    by_src: dict[str, list[dict]] = defaultdict(list)
    for t in tasks:
        if t["source"] in SWEBENCH_DATASETS and t["eval_type"] == "fail_to_pass" and t["source_instance_id"] in preds:
            by_src[t["source"]].append(t)
    out: dict[str, bool] = {}
    for src, ts in by_src.items():
        p = os.path.join(out_dir, f"{run_id}_{src}.jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            for t in ts:
                fh.write(json.dumps(preds[t["source_instance_id"]]) + "\n")
        cmd = swebench_command(src, p, [t["source_instance_id"] for t in ts], f"{run_id}_{src}")
        log.info("running: %s", " ".join(cmd[:8]) + " ...")
        subprocess.run(cmd, check=False, cwd=out_dir)
        for rep in glob.glob(os.path.join(out_dir, f"*.{run_id}_{src}.json")):
            data = json.load(open(rep, encoding="utf-8"))
            ok = set(data.get("resolved_ids", []))
            for t in ts:
                out[t["task_id"]] = t["source_instance_id"] in ok
    return out


# ------------------------------------------------------------------ judges
def judge_flag(submitted: str, expected: str | list[str]) -> bool:
    """CTF judge: exact flag match after whitespace normalisation (NYU CTF / EnIGMA protocol)."""
    exp = [expected] if isinstance(expected, str) else expected
    s = (submitted or "").strip()
    return any(s == e.strip() for e in exp)


def judge_test_generation(tests_on_base: dict[str, str], tests_on_fixed: dict[str, str]) -> dict:
    """SWT-bench criterion over the tests *added by the agent*.

    tests_on_base / tests_on_fixed: {test_name: PASSED|FAILED|ERROR} from running the
    agent's tests on the base commit and on base+gold_patch respectively.
    Success = at least one added test is FAIL->PASS and no added test is PASS->FAIL
    or fails on the fixed code.
    """
    f2p = [t for t in tests_on_fixed if tests_on_fixed[t] == "PASSED" and tests_on_base.get(t) != "PASSED"]
    broken = [t for t in tests_on_fixed if tests_on_fixed[t] != "PASSED"]
    return {"resolved": bool(f2p) and not broken, "fail_to_pass": f2p, "failing_after_fix": broken}
