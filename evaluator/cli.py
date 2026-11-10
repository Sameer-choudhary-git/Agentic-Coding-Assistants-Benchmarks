"""Command-line interface for the evaluator.

Examples::

    python -m evaluator.cli list-tasks
    python -m evaluator.cli show-task BF-01 --json
    python -m evaluator.cli create-workspace BF-01 ../acb-workspaces/try-bf01
    python -m evaluator.cli evaluate --task BF-01 --workspace ../acb-workspaces/try-bf01 --out artifacts/manual/bf01
    python -m evaluator.cli validate --mode local
    python -m evaluator.cli env --mode docker
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from evaluator import EVALUATOR_VERSION
from evaluator.evaluate import evaluate
from evaluator.procs import find_tool, tool_version
from evaluator.runner import ExecutionUnavailable, MODES, make_executor
from evaluator.tasks import TaskError, discover_tasks, get_task
from evaluator.validate import validate_task
from evaluator.workspace import WorkspaceError, create_workspace
from evaluator import swebench


def _default_mode() -> str:
    return os.environ.get("ACB_EVAL_MODE", "docker")


def cmd_list(args: argparse.Namespace) -> int:
    tasks = discover_tasks()
    swe = swebench.list_summaries()
    if args.json:
        custom = [{**t.public_summary(), "benchmark": "custom"} for t in tasks]
        print(json.dumps(custom + swe, indent=None if args.compact else 2))
        return 0
    for task in tasks:
        status = task.validation_status()["status"]
        print(f"{task.id:6} {task.meta['category']:24} {task.meta['difficulty']:7} {status:14} {task.meta['title']}")
    for s in swe:
        print(f"{s['id']:34} {'swebench_verified':24} {s['difficulty']:7} {s['validation']['status']:14} {s['title']}")
    print(f"\n{len(tasks)} custom tasks, {len(swe)} SWE-bench Verified tasks")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    if swebench.is_swebench_id(args.task_id):
        summary = swebench.public_summary(swebench.get_instance(args.task_id))
        print(json.dumps(summary, indent=2) if args.json else summary["prompt"])
        return 0
    task = get_task(args.task_id)
    summary = task.public_summary()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{summary['id']}: {summary['title']} ({summary['category']}, {summary['difficulty']})")
        print(f"version {summary['version']}  tests {summary['test_version']}  task_hash {summary['task_hash'][:16]}")
        print(f"validation: {summary['validation']['status']}\n")
        print(summary["prompt"])
    return 0


def cmd_create_workspace(args: argparse.Namespace) -> int:
    if swebench.is_swebench_id(args.task_id):
        path = swebench.create_workspace(args.task_id, Path(args.destination))
        print(json.dumps({"task_id": args.task_id, "workspace": str(path)}) if args.json else str(path))
        return 0
    task = get_task(args.task_id)
    path = create_workspace(task, Path(args.destination))
    print(json.dumps({"task_id": task.id, "workspace": str(path), **task.hashes()} if args.json else str(path)))
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    context = json.loads(args.context_json) if args.context_json else None
    if swebench.is_swebench_id(args.task):
        report = swebench.evaluate(args.task, Path(args.workspace).resolve(), Path(args.out).resolve(), args.expected_task_hash, context)
    else:
        report = _evaluate_custom(args, context)
    summary = {
        "status": report["status"],
        "success": report["success"],
        "outcome": report["outcome"],
        "error": report["error"],
        "report": str(Path(args.out).resolve() / "report.json"),
    }
    print(json.dumps(summary))
    return 0 if report["status"] == "completed" else 2


def _evaluate_custom(args: argparse.Namespace, context):
    return evaluate(
        args.task,
        Path(args.workspace).resolve(),
        Path(args.out).resolve(),
        args.mode,
        expected_task_hash=args.expected_task_hash,
        run_context=context,
    )


def cmd_validate(args: argparse.Namespace) -> int:
    tasks = [get_task(t) for t in args.task] if args.task else discover_tasks()
    failures = 0
    for task in tasks:
        record = validate_task(task, args.mode, write=not args.dry_run)
        mark = "PASS" if record["passed"] else "FAIL"
        failed_checks = [c["id"] for c in record["checks"] if not c["passed"]]
        print(
            f"[{mark}] {task.id:6} starter={record['starter']['outcome']:<18} reference={record['reference']['outcome']:<18}"
            f" acceptance_tests={record['expected_acceptance_total']}" + (f"  failed: {failed_checks}" if failed_checks else "")
        )
        failures += 0 if record["passed"] else 1
    print(f"\n{len(tasks) - failures}/{len(tasks)} tasks validated (mode={args.mode}, evaluator {EVALUATOR_VERSION})")
    return 0 if failures == 0 else 1


def cmd_env(args: argparse.Namespace) -> int:
    ruff = find_tool("ruff", "ACB_RUFF_BIN")
    semgrep = find_tool("semgrep", "ACB_SEMGREP_BIN")
    info = {
        "evaluator_version": EVALUATOR_VERSION,
        "python": sys.version.split()[0],
        "ruff": tool_version(ruff) if ruff else None,
        "semgrep": tool_version(semgrep) if semgrep else None,
        "semgrep_docker_fallback": os.environ.get("ACB_SEMGREP_DOCKER") == "1",
        "docker_cli": shutil.which("docker"),
        "swebench_harness": swebench.harness_available() or "available",
        "execution": None,
        "execution_error": None,
    }
    try:
        info["execution"] = make_executor(args.mode).describe()
    except ExecutionUnavailable as exc:
        info["execution_error"] = str(exc)
    print(json.dumps(info, indent=2))
    return 0 if info["execution"] else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluator.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list-tasks", help="list all tasks")
    p.add_argument("--json", action="store_true")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show-task", help="show one task's public metadata and frozen prompt")
    p.add_argument("task_id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("create-workspace", help="copy a task's starter files into an empty directory")
    p.add_argument("task_id")
    p.add_argument("destination")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_create_workspace)

    p = sub.add_parser("evaluate", help="evaluate a workspace")
    p.add_argument("--task", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--out", required=True, help="artifact directory for this evaluation")
    p.add_argument("--mode", choices=MODES, default=_default_mode())
    p.add_argument("--expected-task-hash")
    p.add_argument("--context-json", help="JSON object copied into the report (run id, assistant, ...)")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("validate", help="validate tasks (starter fails, reference passes)")
    p.add_argument("--task", action="append", help="task id (repeatable); default: all tasks")
    p.add_argument("--mode", choices=MODES, default=_default_mode())
    p.add_argument("--dry-run", action="store_true", help="do not write validation records")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("env", help="report evaluator tool availability")
    p.add_argument("--mode", choices=MODES, default=_default_mode())
    p.set_defaults(func=cmd_env)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (TaskError, WorkspaceError, swebench.SwebenchError) as exc:
        print(json.dumps({"error": str(exc)}) if getattr(args, "json", False) else f"error: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
