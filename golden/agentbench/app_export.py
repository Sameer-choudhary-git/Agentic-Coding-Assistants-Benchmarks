"""Export the golden tasks the main app can run into ``dataset/app_tasks.json``.

The app (evaluator/swebench.py) clones each task's repository at its base commit, lets an assistant
work the issue, and scores the patch with hidden tests in Docker:

* ``swebench`` harness: SWE-bench Verified, Multilingual and Multimodal (official ``swebench`` package)
* ``swebench_pro`` harness: SWE-bench Pro (the task's published Docker image and run scripts)

Together these cover six domains (bug fix, feature, refactoring, performance, security fix,
frontend/visual). CTF (flag match) and test-generation tasks need other judges and stay in the dataset.

``core`` marks a domain-balanced subset of ``CORE_PER_DOMAIN`` tasks per domain. If
``configs/core_review.yaml`` exists, its manually reviewed core and label corrections are used (each pick
must still pass ``core_eligible``); otherwise ``pick_core`` selects one automatically. Run the core set when the full set is too large: a score on it
is not dominated by bug fixes. Entries follow the ``swebench_pilot/manifest.json`` format, including the
problem-statement hash check.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from collections import defaultdict

APP_FILE = "app_tasks.json"
CORE_PER_DOMAIN = 5
# advisory gate flags that disqualify a task from the core: the issue hints at the fix, or one test decides it
CORE_EXCLUDED_FLAGS = {"solution_hint_partial", "weak_tests_single_f2p"}
CORE_MIN_DOMAIN_CONFIDENCE = 0.7
CORE_MIN_GOLD_QUALITY = 80.0
VERIFIED = "princeton-nlp/SWE-bench_Verified"
SWEBENCH_SOURCES = {
    "swebench_verified": (VERIFIED, "test"),
    "swebench_multilingual": ("SWE-bench/SWE-bench_Multilingual", "test"),
    "swebench_multimodal": ("SWE-bench/SWE-bench_Multimodal", "dev"),
}
PRO_SOURCE = "swebench_pro"


def _as_list(v):
    if isinstance(v, list):
        return v
    if not v:
        return []
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        import ast

        return list(ast.literal_eval(v))


def _harness(r: dict) -> dict | None:
    src = r["source"]
    if src in SWEBENCH_SOURCES:
        dataset, split = SWEBENCH_SOURCES[src]
        return {"type": "swebench", "dataset": dataset, "split": split}
    if src == PRO_SOURCE:
        env = r.get("environment") or {}
        if not env.get("docker_image"):
            return None
        return {
            "type": "swebench_pro",
            "dataset": "ScaleAI/SWE-bench_Pro",
            "docker_image": env["docker_image"],
            "before_repo_set_cmd": env.get("before_repo_set_cmd") or "",
            "selected_test_files_to_run": _as_list(env.get("selected_test_files_to_run")),
            "fail_to_pass": _as_list(r.get("fail_to_pass")),
            "pass_to_pass": _as_list(r.get("pass_to_pass")),
            "test_patch": r.get("test_patch") or "",
        }
    return None


_APP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def app_id(instance_id: str) -> str:
    """The app accepts ids of at most 64 characters from [A-Za-z0-9_-]. SWE-bench Pro ids
    (``instance_<owner>__<repo>-<sha40>-v<sha>``) are longer, so they become ``<owner>__<repo>-<sha10>``."""
    if _APP_ID.match(instance_id):
        return instance_id
    m = re.match(r"^instance_(.+?__.+?)-([0-9a-f]{40})", instance_id)
    base = f"{m.group(1)}-{m.group(2)[:10]}" if m else instance_id
    base = re.sub(r"[^A-Za-z0-9_-]", "-", base)
    if len(base) > 64:
        base = base[:53] + "-" + hashlib.sha256(instance_id.encode()).hexdigest()[:10]
    return base


def core_eligible(e: dict) -> tuple[bool, str]:
    """Stricter than the golden gates, because each core task carries 1/30 of the score."""
    if set(e["gate_flags"]) & CORE_EXCLUDED_FLAGS:
        return False, "advisory gate flag"
    if (e.get("domain_confidence") or 0) < CORE_MIN_DOMAIN_CONFIDENCE:
        return False, "uncertain domain label"
    if e.get("gold_quality_score") is None or e["gold_quality_score"] < CORE_MIN_GOLD_QUALITY:
        return False, "reference fix below the quality bar"
    if not e.get("gold_patch_applies"):
        return False, "reference fix not verified against the base commit"
    if e["fail_to_pass_count"] < 1:
        return False, "no FAIL_TO_PASS test"
    if e["pass_to_pass_count"] < 1:  # about half of SWE-bench Pro ships none upstream
        return False, "no PASS_TO_PASS (regression) tests"
    return True, ""


def pick_core(entries: list[dict], per_domain: int, seed: int, exclude: set[str]) -> set[str]:
    """Seeded, domain-balanced core.

    1. Eligibility: ``core_eligible`` (no leak/weak-test flags, confident domain label, clean reference
       fix that applies to the base commit, at least one FAIL_TO_PASS and one PASS_TO_PASS test); pilot
       tasks are excluded.
    2. Within each domain, shuffle each difficulty tier with the seed, then take tasks round-robin
       easy -> medium -> hard, so every domain gets a similar difficulty mix.
    3. Inside a tier, prefer (in order) a repository not used yet, a source not used yet, human-validated
       upstream, and no possible-contamination flag (created after the contamination cutoff).
    """
    rng = random.Random(seed)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for e in sorted(entries, key=lambda e: e["instance_id"]):
        if e["instance_id"] not in exclude and core_eligible(e)[0]:
            by_domain[e["domain"]].append(e)
    chosen: set[str] = set()
    for dom in sorted(by_domain):
        tiers: dict[str, list[dict]] = defaultdict(list)
        for e in by_domain[dom]:
            tiers[e["tier"]].append(e)
        for bucket in tiers.values():
            rng.shuffle(bucket)
        used_src: dict[str, int] = defaultdict(int)
        used_repo: dict[str, int] = defaultdict(int)
        picked = 0
        while picked < per_domain and any(tiers.values()):
            for tier in ("easy", "medium", "hard"):
                bucket = tiers.get(tier)
                if not bucket or picked >= per_domain:
                    continue
                bucket.sort(key=lambda e: (used_repo[e["repo"]], used_src[e["source"]], not e.get("human_validated"),
                                           "possible_contamination" in e["gate_flags"]))  # stable: ties keep seeded order
                e = bucket.pop(0)
                used_repo[e["repo"]] += 1
                used_src[e["source"]] += 1
                chosen.add(e["instance_id"])
                picked += 1
    return chosen


def _pilot_ids(out_dir: str) -> set[str]:
    """Tasks already in the app's SWE-bench pilot stay there, so they are not core candidates."""
    path = os.path.join(out_dir, "..", "..", "swebench_pilot", "candidates.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {c["instance_id"] for c in json.load(fh)["instances"]}


def load_review(out_dir: str) -> dict | None:
    """configs/core_review.yaml: manual label corrections and the reviewed balanced core."""
    path = os.path.join(out_dir, "..", "configs", "core_review.yaml")
    if not os.path.exists(path):
        return None
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def apply_review(entries: list[dict], review: dict, per_domain: int) -> set[str]:
    """Apply label corrections, then validate and return the reviewed core."""
    by_id = {e["instance_id"]: e for e in entries}
    for iid, fix in (review.get("label_corrections") or {}).items():
        if iid not in by_id:
            raise ValueError(f"core_review: label correction for unknown task {iid}")
        e = by_id[iid]
        e.update(original_domain=e["domain"], domain=fix["to"], subdomain=None, domain_label="manual_review",
                 domain_review_note=fix.get("why"))
    core: set[str] = set()
    for dom, picks in (review.get("core") or {}).items():
        if len(picks) != per_domain:
            raise ValueError(f"core_review: {dom} lists {len(picks)} tasks, expected {per_domain}")
        for iid, why in picks.items():
            e = by_id.get(iid)
            if e is None:
                raise ValueError(f"core_review: unknown task {iid}")
            if e["domain"] != dom:
                raise ValueError(f"core_review: {iid} is {e['domain']}, listed under {dom}")
            ok, reason = core_eligible(e)
            if not ok:
                raise ValueError(f"core_review: {iid} is not core-eligible ({reason})")
            e["core_review_note"] = why
            core.add(iid)
    return core


def _gold_applies(cq: dict) -> bool:
    status = (cq.get("coverage") or {}).get("status") or {}
    return bool(status) and not (status.get("apply_failed") or status.get("fetch_failed"))


def export_app_tasks(golden_jsonl: str, out_dir: str, version: str, seed: int = 20261121) -> str:
    with open(golden_jsonl, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    entries = []
    for r in rows:
        if r["eval_type"] != "fail_to_pass":
            continue
        harness = _harness(r)
        if harness is None:
            continue
        ps = r["problem_statement"]
        cq = r.get("code_quality") or {}
        entries.append({
            "instance_id": app_id(r["source_instance_id"]),
            "source_instance_id": r["source_instance_id"],
            "golden_task_id": r["task_id"],
            "source": r["source"],
            "repo": r["repo"],
            "base_commit": r["base_commit"],
            "language": r.get("language"),
            "difficulty": (r.get("metadata") or {}).get("time_estimate"),
            "tier": r["difficulty"],
            "domain": r["domain"],
            "subdomain": r.get("subdomain"),
            "domain_confidence": r.get("domain_confidence"),
            "gold_quality_score": cq.get("quality_score"),
            "gate_flags": r.get("gate_flags") or [],
            "human_validated": bool(r.get("human_validated")),
            # the code-quality module fetched every touched file at base_commit and applied the reference fix
            "gold_patch_applies": _gold_applies(cq),
            "fail_to_pass_count": len(_as_list(r.get("fail_to_pass"))),
            "pass_to_pass_count": len(_as_list(r.get("pass_to_pass"))),
            "harness": harness,
            "problem_statement_sha256": hashlib.sha256(ps.encode("utf-8")).hexdigest(),
            "problem_statement": ps,
        })
    ids = [e["instance_id"] for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("app task ids are not unique")
    review = load_review(out_dir)
    if review:
        core = apply_review(entries, review, CORE_PER_DOMAIN)
        core_method = f"reviewed ({review.get('reviewer', 'unknown reviewer')}, {review.get('reviewed_on', '')})"
    else:
        core = pick_core(entries, CORE_PER_DOMAIN, seed, _pilot_ids(out_dir))
        core_method = "automatic (pick_core)"
    for e in entries:
        e["core"] = e["instance_id"] in core
        ok, why = core_eligible(e)
        e["core_eligible"] = ok
        if not ok:
            e["core_ineligible_reason"] = why
    entries.sort(key=lambda e: (e["domain"], e["tier"], e["instance_id"]))
    path = os.path.join(out_dir, APP_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"benchmark": "golden", "golden_version": version, "core_per_domain": CORE_PER_DOMAIN, "core_method": core_method,
                   "instances": entries}, fh, indent=2)
    old = os.path.join(out_dir, "app_swebench_verified.json")  # name used before Pro/Multilingual/Multimodal
    if os.path.exists(old):
        os.remove(old)
    return path
