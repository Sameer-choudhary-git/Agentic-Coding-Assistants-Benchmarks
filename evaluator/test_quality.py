"""Evaluation of test-writing tasks.

A submitted test suite is judged on four checks, all of which must pass:

1. ``tests_pass_on_original``: the suite passes against the unmodified target module;
2. ``min_test_count``: at least ``min_tests`` test cases are collected;
3. ``line_coverage``: line coverage of the target module reaches ``min_line_coverage``;
4. ``mutation_score``: the suite fails on at least ``min_mutation_score`` of the hidden mutants
   (seeded faults stored in ``grading/mutants``).

This measures whether the tests are *meaningful* rather than merely present.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

from evaluator.runner import Executor
from evaluator.tasks import Task

_SUSPICIOUS = re.compile(r"hashlib|inspect\.getsource|getsourcelines|read_text\(|read_bytes\(|open\(", re.I)


def _suspicious_tests(eval_dir: Path, test_paths: List[str], target: str) -> List[str]:
    """Flag test files that read the target module's source, which could implement a
    'change detector' instead of behavioural tests. Flags are for manual review only."""
    flagged = []
    module_name = Path(target).stem
    for test_path in test_paths:
        root = eval_dir / test_path
        files = [root] if root.is_file() else sorted(root.rglob("*.py")) if root.is_dir() else []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            if _SUSPICIOUS.search(text) and (module_name in text or target in text):
                flagged.append(path.relative_to(eval_dir).as_posix())
    return flagged


def evaluate_test_writing(task: Task, executor: Executor, eval_dir: Path, artifacts: Path) -> Dict[str, object]:
    spec = task.meta["test_writing"]
    target = spec["target_module"]
    timeout = float(task.meta.get("test_timeout_seconds", 120))
    test_paths = [p for p in spec["test_paths"] if (eval_dir / p).exists()]
    original_source = (eval_dir / target).read_bytes()

    checks: List[Dict[str, object]] = []
    details: Dict[str, object] = {
        "target_module": target,
        "test_paths": spec["test_paths"],
        "thresholds": {
            "min_tests": spec["min_tests"],
            "min_line_coverage": spec["min_line_coverage"],
            "min_mutation_score": spec["min_mutation_score"],
        },
    }

    if test_paths:
        original = executor.run_pytest(
            eval_dir,
            test_paths,
            "tw_original.xml",
            timeout,
            coverage_targets=[target],
            coverage_out="_acb/out/coverage.json",
            allow_conftest=True,
        )
        (artifacts / "tw_original.stdout.txt").write_text(original.proc.stdout, encoding="utf-8")
        (artifacts / "tw_original.stderr.txt").write_text(original.proc.stderr, encoding="utf-8")
        collected = original.total
        passed_original = (
            original.proc.exit_code == 0
            and not original.proc.timed_out
            and original.failed == 0
            and original.errors == 0
            and original.passed > 0
        )
        coverage_path = eval_dir / "_acb" / "out" / "coverage.json"
        coverage = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.exists() else None
        details["original_run"] = {
            **original.proc.to_dict(),
            "passed": original.passed,
            "failed": original.failed,
            "errors": original.errors,
            "skipped": original.skipped,
            "tests": original.tests,
        }
    else:
        collected = 0
        passed_original = False
        coverage = None
        details["original_run"] = {"error": "no test files found at the expected paths"}

    line_coverage = coverage.get("line_coverage") if coverage else None
    details["coverage"] = coverage

    mutants_dir = task.grading_dir / "mutants"
    manifest = json.loads((mutants_dir / "manifest.json").read_text(encoding="utf-8"))
    mutant_results = []
    if passed_original:
        for mutant in manifest["mutants"]:
            (eval_dir / target).write_bytes((mutants_dir / mutant["file"]).read_bytes())
            outcome = executor.run_pytest(eval_dir, test_paths, f"mutant_{mutant['id']}.xml", timeout, allow_conftest=True, fail_fast=True)
            killed = outcome.proc.timed_out or outcome.proc.exit_code not in (0, 5)
            mutant_results.append(
                {
                    "id": mutant["id"],
                    "description": mutant["description"],
                    "killed": bool(killed),
                    "exit_code": outcome.proc.exit_code,
                    "timed_out": outcome.proc.timed_out,
                    "failed_tests": [t["id"] for t in outcome.tests if t["outcome"] in ("failed", "error")][:10],
                }
            )
        (eval_dir / target).write_bytes(original_source)
    killed = sum(1 for m in mutant_results if m["killed"])
    mutation_score = (killed / len(manifest["mutants"])) if passed_original and manifest["mutants"] else None
    details["mutants"] = mutant_results
    details["mutants_total"] = len(manifest["mutants"])
    details["mutants_killed"] = killed if passed_original else None
    details["mutation_score"] = mutation_score
    details["line_coverage"] = line_coverage
    details["tests_collected"] = collected
    details["review_flags"] = _suspicious_tests(eval_dir, test_paths, target)

    def check(check_id: str, ok: bool, value: object, threshold: object, message: str) -> None:
        checks.append(
            {
                "id": check_id,
                "name": check_id,
                "outcome": "passed" if ok else "failed",
                "value": value,
                "threshold": threshold,
                "message": None if ok else message,
                "duration_s": 0.0,
            }
        )

    check(
        "tests_pass_on_original",
        passed_original,
        passed_original,
        True,
        "submitted tests do not pass against the original module (or no tests were found)",
    )
    check("min_test_count", collected >= spec["min_tests"], collected, spec["min_tests"], f"only {collected} test cases collected")
    check(
        "line_coverage",
        line_coverage is not None and passed_original and line_coverage >= spec["min_line_coverage"],
        None if line_coverage is None else round(line_coverage, 4),
        spec["min_line_coverage"],
        "line coverage below threshold (coverage only counts when the suite passes)",
    )
    check(
        "mutation_score",
        mutation_score is not None and mutation_score >= spec["min_mutation_score"],
        None if mutation_score is None else round(mutation_score, 4),
        spec["min_mutation_score"],
        "too few mutants detected (not computed when the suite fails on the original module)",
    )
    passed = sum(1 for c in checks if c["outcome"] == "passed")
    acceptance = {
        "status": "ran",
        "kind": "test_quality_checks",
        "passed": passed,
        "failed": len(checks) - passed,
        "errors": 0,
        "skipped": 0,
        "total": len(checks),
        "expected_total": len(checks),
        "missing": 0,
        "tests": checks,
    }
    return {"acceptance": acceptance, "test_quality": details}
