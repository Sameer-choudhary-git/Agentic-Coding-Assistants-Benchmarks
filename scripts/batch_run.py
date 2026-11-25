"""Run an automated (headless) experiment end to end through the app's API.

For every run of the experiment, in the experiment's own (randomised) order:
prepare the workspace -> run the assistant's headless CLI (/automate) -> the app queues scoring.
The agent of the next run works while the previous run is being scored. The script then waits
until every run is scored and prints a summary. Progress is appended to a log file.

Usage (the app must be running, started from Ubuntu with ACB_ENABLE_AUTOMATION=1):
    python scripts/batch_run.py --name "Claude Code core-12" --assistant claude_code \
        --tasks django__django-16801 caddyserver__caddy-6115 ...
    python scripts/batch_run.py --experiment <id>        # resume an existing experiment

Failures caused by tooling (evaluator/environment) are re-scored once; agent failures are kept as data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LOG: Path | None = None


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc):%H:%M:%S}Z {msg}"
    print(line, flush=True)
    if LOG:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def api(base: str, method: str, path: str, body: dict | None = None, timeout: float = 60) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}


def runs_of(base: str, exp: str) -> list[dict]:
    _, d = api(base, "GET", f"/runs?experimentId={exp}&limit=500")
    runs = d.get("runs", d) if isinstance(d, dict) else d
    return runs


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:4100/api/v1")
    ap.add_argument("--experiment", help="resume this experiment id")
    ap.add_argument("--name")
    ap.add_argument("--assistant", default="claude_code")
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--attempts", type=int, default=1)
    ap.add_argument("--max-runs", type=int, help="run at most this many agent runs now; resume later with --experiment")
    ap.add_argument("--log", type=Path, default=Path("artifacts/batch_run.log"))
    a = ap.parse_args()
    LOG = a.log
    LOG.parent.mkdir(parents=True, exist_ok=True)
    base = a.base

    code, h = api(base, "GET", "/health")
    if code != 200 or not h.get("automationEnabled"):
        sys.exit(f"app not reachable or automation disabled: {code} {h}")

    exp = a.experiment
    if not exp:
        if not (a.name and a.tasks):
            sys.exit("--name and --tasks are required to create an experiment")
        code, d = api(base, "POST", "/experiments", {
            "name": a.name, "description": "Automated headless batch (scripts/batch_run.py)",
            "taskIds": a.tasks, "assistantIds": [a.assistant], "attempts": a.attempts,
            "executionMode": "automated", "evalMode": "docker", "randomizeOrder": True,
        })
        if code != 201:
            sys.exit(f"create failed: {code} {d}")
        exp = d["experiment"]["id"]
        api(base, "POST", f"/experiments/{exp}/start")
        log(f"created experiment {exp} ({len(a.tasks)} tasks x {a.attempts} attempt(s))")
    else:
        log(f"resuming experiment {exp}")

    # Runs come back in the experiment's planned order.
    todo = [r for r in runs_of(base, exp) if r["status"] in ("planned", "ready")]
    left = len(todo)
    if a.max_runs is not None:
        todo = todo[: max(a.max_runs, 0)]
    log(f"{len(todo)} run(s) to execute now, {left - len(todo)} left after this (resume: --experiment {exp})")
    for i, r in enumerate(todo, 1):
        rid, task = r["id"], r["taskId"]
        if r["status"] == "planned":
            log(f"[{i}/{len(todo)}] {task}: preparing workspace")
            code, d = api(base, "POST", f"/runs/{rid}/prepare", timeout=1800)
            if code >= 300:
                log(f"[{i}/{len(todo)}] {task}: prepare failed {code} {str(d)[:300]}")
                continue
        log(f"[{i}/{len(todo)}] {task}: running agent")
        t0 = time.time()
        code, d = api(base, "POST", f"/runs/{rid}/automate", timeout=3 * 3600)
        st = (d.get("run") or {}).get("status")
        log(f"[{i}/{len(todo)}] {task}: agent done in {time.time() - t0:.0f}s -> {code} {st} {str(d.get('error') or '')[:200]}")

    # Wait for scoring; re-score tooling failures once, only for runs executed now (older failures were
    # already re-scored by an earlier invocation; re-score those from the run page after fixing the cause).
    rescored: set[str] = {r["id"] for r in runs_of(base, exp) if r["id"] not in {t["id"] for t in todo}}
    while True:
        runs = runs_of(base, exp)
        busy = [r for r in runs if r["status"] in ("submitted", "evaluating", "running")]
        for r in runs:
            if r["status"] == "failed" and r.get("failureClass") == "evaluator_error" and r["id"] not in rescored:
                rescored.add(r["id"])
                log(f"{r['taskId']}: tooling failure, re-scoring once")
                api(base, "POST", f"/runs/{r['id']}/evaluate")
                busy.append(r)
        if not busy:
            break
        time.sleep(30)

    log("summary:")
    for r in runs_of(base, exp):
        log(f"  {r['taskId']:<40} {r['status']:<10} outcome={r.get('outcome')} success={r.get('success')} "
            f"time={r.get('wallClockSeconds')}s")
    log(f"done: experiment {exp}")


if __name__ == "__main__":
    main()
