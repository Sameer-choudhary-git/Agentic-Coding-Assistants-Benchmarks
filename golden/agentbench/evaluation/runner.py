"""Evaluation runner: outcomes + code quality + localisation, stratified by domain."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from ..code_quality.fetch import FileFetcher
from ..code_quality.scorer import QualityAssessor
from ..gates import is_admitted
from .metrics import localization
from .published import PublishedRun, load_registry

log = logging.getLogger(__name__)
QUALITY_BAR = 80.0


def load_golden(cfg: dict) -> list[dict]:
    path = os.path.join(cfg["paths"]["out"], f"golden_v{cfg['version']}.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _assess_rows(rows: list[dict], tasks: dict[str, dict], qa: QualityAssessor, workers: int) -> None:
    def run(r: dict) -> None:
        t = tasks[r["task_id"]]
        patch = r.pop("_patch", "")
        r["has_patch"] = bool(patch.strip())
        if not patch.strip():
            return
        loc = localization(patch, t["gold_patch"])
        r.update({f"loc_{k}": v for k, v in loc.items()})
        try:
            q = qa.assess(t["repo"], t["base_commit"], patch, reference_patch=t["gold_patch"])
        except Exception as e:  # noqa: BLE001
            r["quality_error"] = repr(e)
            return
        r["quality_score"] = q["quality_score"]
        for k, v in q["subscores"].items():
            r[f"q_{k}"] = v
        r["size_ratio"] = q["size_ratio_vs_reference"]
        r["tests_included"] = q["tests_included"]
        r["stray_files"] = len(q.get("stray_files", []))
        r["changed_lines"] = q["changed_source_lines"]
        r["lint_new"] = json.dumps(q["lint_new"])
        r["bandit_new"] = json.dumps(q["bandit_new"])
        r["security_patterns"] = json.dumps(q["security_patterns"])
        r["smells"] = json.dumps(q["smells"])
        r["new_complex_functions"] = len(q["new_complex_functions"])
        r["analyzed_files"] = q["coverage"]["analyzed_files"]

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(run, rows))


def evaluate_published(cfg: dict, golden: list[dict]) -> pd.DataFrame:
    reg = load_registry()
    gold_by_iid = {t["source_instance_id"]: t for t in golden
                   if t["source"] == "swebench_verified" and t["eval_type"] == "fail_to_pass"}
    # full Verified pool (admitted, domain-labelled) for higher-powered domain analysis
    pool_rows: list[dict] = []
    pool_path = os.path.join(cfg["paths"]["cache"], "pool.pkl")
    if os.path.exists(pool_path):
        import pickle
        pool, _ = pickle.load(open(pool_path, "rb"))
        pool_rows = [t.to_dict() for t in pool if t.source == "swebench_verified" and is_admitted(t)]
    tasks = {t["task_id"]: t for t in pool_rows}
    tasks.update({t["task_id"]: t for t in golden})

    qa = QualityAssessor(FileFetcher(cfg["paths"]["cache"], cfg["code_quality"]["max_file_bytes"]))
    rows: list[dict] = []
    for spec in reg["agents"]:
        run = PublishedRun(spec, reg, cfg["paths"]["cache"])
        res = run.resolved()
        if res is None:
            log.warning("no results for %s - skipped", spec["id"])
            continue
        patches = run.patches(sorted(gold_by_iid))
        golden_rows = []
        for iid, t in gold_by_iid.items():
            golden_rows.append({"agent": spec["id"], "family": spec["family"], "scope": "golden",
                                "task_id": t["task_id"], "domain": t["domain"], "subdomain": t["subdomain"],
                                "difficulty": t["difficulty"],
                                "language": t["language"], "resolved": run.is_resolved(res, iid),
                                "_patch": patches.get(iid, "")})
        _assess_rows(golden_rows, tasks, qa, cfg["code_quality"]["fetch_workers"])
        rows += golden_rows
        for t in pool_rows:
            rows.append({"agent": spec["id"], "family": spec["family"], "scope": "verified_pool",
                         "task_id": t["task_id"], "domain": t["domain"], "subdomain": t["subdomain"],
                         "difficulty": t["difficulty"], "repo": t["repo"],
                         "language": t["language"], "resolved": run.is_resolved(res, t["source_instance_id"])})
        log.info("%-28s golden resolved %d/%d", spec["id"], sum(r["resolved"] for r in golden_rows), len(golden_rows))

    # gold-patch baseline row per golden task
    for iid, t in gold_by_iid.items():
        cq = t.get("code_quality") or {}
        if "quality_score" in cq:
            rows.append({"agent": "gold", "family": "human reference", "scope": "golden", "task_id": t["task_id"],
                         "domain": t["domain"], "difficulty": t["difficulty"], "language": t["language"],
                         "resolved": True, "has_patch": True, "quality_score": cq["quality_score"],
                         **{f"q_{k}": v for k, v in cq["subscores"].items()},
                         "tests_included": cq.get("tests_included"), "changed_lines": cq.get("changed_source_lines"),
                         "lint_new": json.dumps(cq.get("lint_new", {})), "bandit_new": json.dumps(cq.get("bandit_new", {})),
                         "security_patterns": json.dumps(cq.get("security_patterns", {})),
                         "smells": json.dumps(cq.get("smells", {})),
                         "new_complex_functions": len(cq.get("new_complex_functions", []))})
    return pd.DataFrame(rows)


def evaluate_predictions(cfg: dict, golden: list[dict], pred_path: str, results_path: str | None,
                         run_harness: bool) -> pd.DataFrame:
    preds: dict[str, dict] = {}
    with open(pred_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                preds[d.get("task_id") or d["instance_id"]] = d
    by_key = {}
    for t in golden:
        by_key[t["task_id"]] = t
        by_key.setdefault(t["source_instance_id"], t)
    matched = {by_key[k]["task_id"]: v for k, v in preds.items() if k in by_key}
    outcomes: dict[str, bool] = {}
    if results_path:
        outcomes = {by_key[k]["task_id"]: bool(v) for k, v in json.load(open(results_path)).items() if k in by_key}
    for tid, p in matched.items():
        if "resolved" in p:
            outcomes[tid] = bool(p["resolved"])
    if run_harness:
        from .harness import run_swebench
        outcomes.update(run_swebench([by_key[t] for t in matched],
                                     {by_key[t]["source_instance_id"]: p for t, p in matched.items()},
                                     os.path.join(cfg["paths"]["reports"], "harness"), "agentbench"))
    tasks = {t["task_id"]: t for t in golden}
    rows = [{"agent": p.get("model_name_or_path", "user"), "family": "user", "scope": "golden", "task_id": tid,
             "domain": tasks[tid]["domain"], "difficulty": tasks[tid]["difficulty"], "language": tasks[tid]["language"],
             "resolved": outcomes.get(tid), "_patch": p.get("model_patch", "")} for tid, p in matched.items()]
    code_rows = [r for r in rows if tasks[r["task_id"]]["eval_type"] == "fail_to_pass"]
    qa = QualityAssessor(FileFetcher(cfg["paths"]["cache"]))
    _assess_rows(code_rows, tasks, qa, cfg["code_quality"]["fetch_workers"])
    log.info("matched %d/%d predictions to golden tasks", len(matched), len(preds))
    return pd.DataFrame(rows)


def evaluate(cfg: dict, predictions: str | None = None, results: str | None = None,
             published: bool = False, run_harness: bool = False) -> None:
    golden = load_golden(cfg)
    out_dir = os.path.join(cfg["paths"]["reports"], "eval")
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    if published:
        frames.append(evaluate_published(cfg, golden))
    if predictions:
        frames.append(evaluate_predictions(cfg, golden, predictions, results, run_harness))
    if not frames:
        raise SystemExit("nothing to evaluate: pass --published and/or --predictions")
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(os.path.join(out_dir, "instance_results.csv"), index=False)
    log.info("wrote %d rows to %s", len(df), out_dir)
