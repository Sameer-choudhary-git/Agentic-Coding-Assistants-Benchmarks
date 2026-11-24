"""Score an assistant's workspace for a golden / SWE-bench task outside the app (pilot runs).

Runs the app's own evaluator (hidden tests in Docker + patch code quality) on the workspace's changes and
prints a one-line summary. Run from WSL, e.g.:
    ACB_SWEBENCH_PRO_SCRIPTS=~/SWE-bench_Pro-os/run_scripts ~/acb-venv/bin/python \\
        golden/scripts/score_workspace.py caddyserver__caddy-6115 /mnt/d/.../acb-pilot/caddy ~/acb-pilot-out/caddy
Pilot results are not study data: study runs go through the app so timing, prompt and version are recorded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluator import swebench as S  # noqa: E402


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: score_workspace.py <app task id> <workspace> <output dir>")
    task, ws, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    rep = S.evaluate(task, ws, out, run_context={"run_id": "pilot", "assistant_id": "pilot"})
    cq = rep.get("code_quality") or {}
    print(json.dumps({
        "task": task,
        "outcome": rep.get("outcome"),
        "resolved": rep.get("success"),
        "fail_to_pass": f"{(rep.get('acceptance') or {}).get('passed')}/{(rep.get('acceptance') or {}).get('total')}",
        "pass_to_pass_failed": (rep.get("regression") or {}).get("failed"),
        "lines": f"+{(rep.get('diff') or {}).get('lines_added')}/-{(rep.get('diff') or {}).get('lines_removed')}",
        "quality": cq.get("quality_score"),
        "reference_quality": cq.get("gold_quality_score"),
        "quality_findings": {k: cq.get(k) for k in ("lint_new", "bandit_new", "security_patterns", "smells", "stray_files") if cq.get(k)},
        "error": rep.get("error"),
        "report": str(out / "report.json"),
    }, indent=1))


if __name__ == "__main__":
    main()
