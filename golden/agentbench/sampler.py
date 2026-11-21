"""Stratified sampling of the golden set, plus derivation of test-generation tasks."""
from __future__ import annotations

import copy
import random
from collections import Counter, defaultdict

from .diffutil import is_test_path, parse_diff
from .gates import is_admitted
from .schema import GoldenTask

MIN_CONFIDENCE = 0.5


def _eligible(t: GoldenTask) -> bool:
    return is_admitted(t) and t.domain_confidence >= MIN_CONFIDENCE


def stratified_pick(pool: list[GoldenTask], quota: int, priority: dict[str, int], rng: random.Random,
                    max_repo_share: float = 0.15, repo_n: Counter | None = None,
                    repo_cap: int | None = None) -> list[GoldenTask]:
    """Round-robin over (language, difficulty) strata; within a stratum prefer
    human-validated, higher-priority sources and higher classifier confidence.
    A per-repository cap keeps any single project from dominating a domain."""
    cells: dict[tuple, list[GoldenTask]] = defaultdict(list)
    for t in pool:
        cells[(t.language, t.difficulty)].append(t)
    for c in cells.values():
        rng.shuffle(c)
        c.sort(key=lambda t: (not t.human_validated, priority.get(t.source, 99), -t.domain_confidence))
    keys = sorted(cells)
    rng.shuffle(keys)
    repo_cap = repo_cap or max(3, int(quota * max_repo_share))
    picked: list[GoldenTask] = []
    repo_n = repo_n if repo_n is not None else Counter()
    while len(picked) < quota and any(cells[k] for k in keys):
        progressed = False
        for k in keys:
            while cells[k]:
                t = cells[k].pop(0)
                if t.repo and repo_n[t.repo] >= repo_cap:
                    continue
                picked.append(t)
                repo_n[t.repo] += 1
                progressed = True
                break
            if len(picked) >= quota:
                break
        if not progressed:
            break
    return picked


def derive_test_generation(t: GoldenTask) -> GoldenTask | None:
    """SWT-bench-style task: given the issue, write tests that FAIL on the base
    commit and PASS once the (hidden) gold fix is applied."""
    tfiles = parse_diff(t.test_patch)
    if not tfiles or not all(is_test_path(f.path) for f in tfiles) or not t.fail_to_pass:
        return None
    d = copy.deepcopy(t)
    d.task_id = f"{t.source}::testgen::{t.source_instance_id}"
    d.domain = "test_generation"
    d.subdomain = "issue_reproduction_test"
    d.eval_type = "test_generation"
    d.domain_confidence = 1.0
    d.domain_evidence = [f"derived from {t.task_id} (reference tests = upstream test_patch)"]
    d.problem_statement = (
        "Write one or more tests that reproduce the issue below. Your tests must FAIL on the "
        "current code and PASS once the issue is fixed. Do not modify non-test source files.\n\n"
        + t.problem_statement)
    d.metadata = {**t.metadata, "derived_from": t.task_id, "reference_tests": "test_patch",
                  "hidden_fix": "gold_patch"}
    return d


def pick_domain(pool: list[GoldenTask], quota: int, prio: dict[str, int], rng: random.Random,
                anchors: dict[str, int] | None = None) -> list[GoldenTask]:
    """Anchored stratified sampling: first guarantee per-source minimums (e.g. SWE-bench
    Verified, so results stay comparable with public leaderboards), then fill the
    remaining quota stratified over the whole pool. If the per-repo cap starves the
    quota (few-repo sources such as Multimodal), relax the cap step by step."""
    repo_cap = max(3, int(quota * 0.15))
    repo_n: Counter = Counter()
    picked: list[GoldenTask] = []
    for src, n in (anchors or {}).items():
        sub = [t for t in pool if t.source == src]
        picked += stratified_pick(sub, min(n, quota - len(picked)), prio, rng, repo_n=repo_n, repo_cap=repo_cap)
    while len(picked) < quota:
        chosen = {id(t) for t in picked}
        rest = [t for t in pool if id(t) not in chosen]
        more = stratified_pick(rest, quota - len(picked), prio, rng, repo_n=repo_n, repo_cap=repo_cap)
        picked += more
        if len(picked) >= quota or repo_cap >= quota or not rest:
            break
        repo_cap = int(repo_cap * 1.5) + 1
    return picked


def build_golden(tasks: list[GoldenTask], quotas: dict[str, int], priority_list: list[str],
                 seed: int, anchors: dict[str, dict[str, int]] | None = None) -> list[GoldenTask]:
    rng = random.Random(seed)
    prio = {s: i for i, s in enumerate(priority_list)}
    eligible = [t for t in tasks if _eligible(t)]
    golden: list[GoldenTask] = []
    used: set[str] = set()
    for domain, quota in quotas.items():
        if domain == "test_generation":
            continue
        pool = [t for t in eligible if t.domain == domain]
        picked = pick_domain(pool, quota, prio, rng, (anchors or {}).get(domain))
        golden.extend(picked)
        used.update(t.source_instance_id for t in picked)

    if quotas.get("test_generation"):
        # derive from human-validated bug fixes not already in the golden set
        base = [t for t in eligible if t.domain == "bug_fix" and t.human_validated
                and t.source in ("swebench_verified", "swebench_multilingual")
                and t.source_instance_id not in used]
        derived = [d for d in (derive_test_generation(t) for t in base) if d]
        golden.extend(pick_domain(derived, quotas["test_generation"], prio, rng,
                                  (anchors or {}).get("test_generation")))
    golden.sort(key=lambda t: (list(quotas).index(t.domain), t.task_id))
    return golden
