"""End-to-end golden-dataset build pipeline."""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import os
import pickle
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import jsonschema
import pandas as pd
import yaml

from . import difficulty
from .code_quality.fetch import FileFetcher
from .code_quality.scorer import QualityAssessor
from .gates import BLOCKING, apply_gates, is_admitted
from .sampler import build_golden
from .schema import JSON_SCHEMA, GoldenTask
from .sources import load_all

log = logging.getLogger(__name__)


def load_config(path: str = "configs/golden.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_pool(cfg: dict, force_download: bool = False) -> tuple[list[GoldenTask], dict]:
    tasks, manifest = load_all(cfg, force=force_download)
    g = dict(cfg["quality_gates"])
    g["_source_priority"] = cfg["source_priority"]
    gate_stats = apply_gates(tasks, g)
    cal = difficulty.calibrate(tasks)
    difficulty.assign(tasks, cal)
    meta = {"sources": manifest, "gate_stats": gate_stats, "difficulty_calibration": cal}
    pool_path = os.path.join(cfg["paths"]["cache"], "pool.pkl")
    os.makedirs(cfg["paths"]["cache"], exist_ok=True)
    with open(pool_path, "wb") as fh:
        pickle.dump((tasks, meta), fh)
    return tasks, meta


def load_pool(cfg: dict) -> tuple[list[GoldenTask], dict]:
    with open(os.path.join(cfg["paths"]["cache"], "pool.pkl"), "rb") as fh:
        return pickle.load(fh)


def profile_quality(tasks: list[GoldenTask], cfg: dict) -> None:
    qa = QualityAssessor(FileFetcher(cfg["paths"]["cache"], cfg["code_quality"]["max_file_bytes"]))
    todo = [t for t in tasks if t.eval_type == "fail_to_pass" and t.gold_patch]

    def run(t: GoldenTask) -> None:
        try:
            rep = qa.assess(t.repo, t.base_commit, t.gold_patch)
            rep.pop("files", None)
            t.code_quality = rep
        except Exception as e:  # noqa: BLE001
            t.code_quality = {"error": repr(e)}

    with ThreadPoolExecutor(cfg["code_quality"]["fetch_workers"]) as ex:
        for i, _ in enumerate(ex.map(run, todo), 1):
            if i % 50 == 0:
                log.info("quality profiled %d/%d", i, len(todo))


def validate(tasks: list[GoldenTask]) -> list[str]:
    errs = []
    v = jsonschema.Draft202012Validator(JSON_SCHEMA)
    for t in tasks:
        for e in v.iter_errors(t.to_dict()):
            errs.append(f"{t.task_id}: {e.message[:200]}")
    ids = Counter(t.task_id for t in tasks)
    errs += [f"duplicate task_id {k}" for k, n in ids.items() if n > 1]
    return errs


def export(golden: list[GoldenTask], pool: list[GoldenTask], meta: dict, cfg: dict) -> dict:
    out = cfg["paths"]["out"]
    os.makedirs(out, exist_ok=True)
    ver = cfg["version"]
    rows = [t.to_dict() for t in golden]
    jl = os.path.join(out, f"golden_v{ver}.jsonl")
    with open(jl, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    flat = pd.DataFrame([{**r, **{k: json.dumps(r[k], ensure_ascii=False) for k in
                                  ("patch_stats", "environment", "metadata", "code_quality",
                                   "domain_evidence", "gate_flags", "fail_to_pass", "pass_to_pass")}} for r in rows])
    flat.to_parquet(os.path.join(out, f"golden_v{ver}.parquet"), index=False)

    # per-domain splits
    os.makedirs(os.path.join(out, "by_domain"), exist_ok=True)
    for dom in sorted({t.domain for t in golden}):
        with open(os.path.join(out, "by_domain", f"{dom}.jsonl"), "w", encoding="utf-8") as fh:
            for r in rows:
                if r["domain"] == dom:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # human review sheet (golden = machine-curated; this closes the loop with annotators)
    with open(os.path.join(out, "review_sheet.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "domain", "subdomain", "domain_confidence", "difficulty", "language", "repo",
                    "human_validated_upstream", "advisory_flags", "issue_excerpt",
                    "REVIEW_domain_ok(y/n)", "REVIEW_issue_well_specified(0-3)", "REVIEW_tests_valid(0-3)", "REVIEW_notes"])
        for t in golden:
            w.writerow([t.task_id, t.domain, t.subdomain, t.domain_confidence, t.difficulty, t.language, t.repo,
                        t.human_validated, ";".join(t.gate_flags),
                        " ".join(t.problem_statement.split())[:300], "", "", "", ""])

    # tasks the main app can run (evaluator/swebench.py reads this file)
    from .app_export import export_app_tasks
    app_file = export_app_tasks(jl, out, ver)

    stats = summarise(golden, pool, meta)
    manifest = {
        "name": "AgentBench-Golden", "version": ver, "seed": cfg["seed"],
        "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_tasks": len(golden), "files": {"jsonl": jl, "app_tasks": app_file}, **meta, "summary": stats,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    return manifest


def summarise(golden: list[GoldenTask], pool: list[GoldenTask], meta: dict) -> dict:
    def c(f):
        return dict(Counter(f(t) for t in golden).most_common())
    q = [t.code_quality.get("quality_score") for t in golden if t.code_quality.get("quality_score") is not None]
    return {
        "pool_size": len(pool),
        "pool_admitted": sum(is_admitted(t) for t in pool),
        "by_domain": c(lambda t: t.domain),
        "by_source": c(lambda t: t.source),
        "by_language": c(lambda t: t.language),
        "by_difficulty": c(lambda t: t.difficulty),
        "by_domain_difficulty": {f"{k[0]}|{k[1]}": v for k, v in Counter((t.domain, t.difficulty) for t in golden).items()},
        "by_subdomain": c(lambda t: f"{t.domain}/{t.subdomain}"),
        "repos": len({t.repo for t in golden if t.repo}),
        "human_validated_share": round(sum(t.human_validated for t in golden) / max(len(golden), 1), 3),
        "gold_quality_mean": round(sum(q) / len(q), 2) if q else None,
        "gold_quality_lt80": sum(x < 80 for x in q),
        "rejection_reasons_pool": dict(Counter(f for t in pool for f in t.gate_flags if f in BLOCKING).most_common()),
    }


def build(cfg: dict, *, reuse_pool: bool = False, skip_quality: bool = False) -> dict:
    if reuse_pool and os.path.exists(os.path.join(cfg["paths"]["cache"], "pool.pkl")):
        pool, meta = load_pool(cfg)
    else:
        pool, meta = build_pool(cfg)
    golden = build_golden(pool, cfg["quotas"], cfg["source_priority"], cfg["seed"], cfg.get("anchors"))
    log.info("golden set: %d tasks %s", len(golden), dict(Counter(t.domain for t in golden)))
    if not skip_quality:
        profile_quality(golden, cfg)
    errs = validate(golden)
    if errs:
        raise SystemExit("schema validation failed:\n" + "\n".join(errs[:20]))
    manifest = export(golden, pool, meta, cfg)
    from .datacard import write_datacard
    write_datacard(manifest, golden, cfg)
    return manifest
