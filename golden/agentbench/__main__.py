"""CLI: python -m agentbench <command>

  build      download sources, gate, classify, sample, quality-profile, export golden set
  quality    score an arbitrary patch file against repo@commit
  evaluate   evaluate predictions / published agent results on the golden set
  export-app write dataset/app_swebench_verified.json for the main app (no download)
  report     regenerate research report tables and figures
  all        build + evaluate + report
"""
from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentbench")
    p.add_argument("--config", default="configs/golden.yaml")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--reuse-pool", action="store_true", help="skip download/gating if a cached pool exists")
    b.add_argument("--skip-quality", action="store_true")

    q = sub.add_parser("quality")
    q.add_argument("--repo", required=True)
    q.add_argument("--commit", required=True)
    q.add_argument("--patch", required=True, help="path to unified diff")
    q.add_argument("--reference", help="optional reference (gold) patch for size comparison")

    e = sub.add_parser("evaluate")
    e.add_argument("--predictions", help="JSONL predictions {instance_id, model_patch, model_name_or_path[, resolved]}")
    e.add_argument("--results", help="optional JSON {instance_id: bool} execution results for --predictions")
    e.add_argument("--published", action="store_true", help="import published SWE-bench agent runs")
    e.add_argument("--run-harness", action="store_true", help="execute tests via the swebench docker harness")


    sub.add_parser("export-app", help="write the app task file from the existing golden JSONL")
    sub.add_parser("report")
    sub.add_parser("all")

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .pipeline import build, load_config
    cfg = load_config(a.config)

    if a.cmd in ("build", "all"):
        m = build(cfg, reuse_pool=getattr(a, "reuse_pool", False), skip_quality=getattr(a, "skip_quality", False))
        print(json.dumps(m["summary"], indent=2))
    if a.cmd == "quality":
        from .code_quality.fetch import FileFetcher
        from .code_quality.scorer import QualityAssessor
        qa = QualityAssessor(FileFetcher(cfg["paths"]["cache"]))
        ref = open(a.reference, encoding="utf-8").read() if a.reference else None
        print(json.dumps(qa.assess(a.repo, a.commit, open(a.patch, encoding="utf-8").read(), ref), indent=2))
    if a.cmd in ("evaluate", "all"):
        from .evaluation.runner import evaluate
        evaluate(cfg, predictions=getattr(a, "predictions", None), results=getattr(a, "results", None),
                 published=getattr(a, "published", False) or a.cmd == "all",
                 run_harness=getattr(a, "run_harness", False))
    if a.cmd == "export-app":
        from .app_export import export_app_tasks
        out = cfg["paths"]["out"]
        print(export_app_tasks(f"{out}/golden_v{cfg['version']}.jsonl", out, cfg["version"]))
    if a.cmd in ("report", "all"):
        from .evaluation.report import make_report
        make_report(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
