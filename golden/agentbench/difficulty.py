"""Difficulty normalisation across benchmarks.

Sources label difficulty differently (SWE-bench Verified: human time-to-fix
buckets; SWE-Bench++: easy/medium/hard; SWE-rebench: LLM score; Pro: a "hard"
subset flag). For tasks with no label we fit a transparent patch-complexity
model *calibrated on the human-labelled tasks* and report its agreement.
"""
from __future__ import annotations

import math
from itertools import product

from .schema import GoldenTask

ORD = {"easy": 0, "medium": 1, "hard": 2}
INV = {v: k for k, v in ORD.items()}


def complexity_score(ps: dict) -> float:
    return (math.log1p(ps.get("changed", 0))
            + 0.6 * math.log1p(max(ps.get("source_files", 0) - 1, 0))
            + 0.35 * math.log1p(max(ps.get("hunks", 0) - 1, 0)))


def _bucket(s: float, t1: float, t2: float) -> int:
    return 0 if s < t1 else (1 if s < t2 else 2)


def calibrate(tasks: list[GoldenTask]) -> dict:
    """Grid-search two thresholds maximising agreement with human labels."""
    lab = [(complexity_score(t.patch_stats), ORD[t.difficulty]) for t in tasks
           if t.difficulty_source == "source_label" and t.source in ("swebench_verified", "swebench_plusplus")
           and t.difficulty in ORD and t.patch_stats]
    if len(lab) < 30:
        return {"t1": 2.5, "t2": 4.0, "n": len(lab), "accuracy": None}
    grid = [x / 10 for x in range(10, 80)]
    best = (-1.0, 2.5, 4.0)
    for t1, t2 in product(grid, grid):
        if t2 <= t1:
            continue
        # balanced accuracy so the majority class does not dominate
        per = {0: [0, 0], 1: [0, 0], 2: [0, 0]}
        for s, y in lab:
            per[y][1] += 1
            per[y][0] += _bucket(s, t1, t2) == y
        bacc = sum(c / n for c, n in per.values() if n) / sum(1 for _, n in per.values() if n)
        if bacc > best[0]:
            best = (bacc, t1, t2)
    bacc, t1, t2 = best
    acc = sum(_bucket(s, t1, t2) == y for s, y in lab) / len(lab)
    within1 = sum(abs(_bucket(s, t1, t2) - y) <= 1 for s, y in lab) / len(lab)
    rho = _spearman([s for s, _ in lab], [y for _, y in lab])
    return {"t1": t1, "t2": t2, "n": len(lab), "balanced_accuracy": round(bacc, 3),
            "accuracy": round(acc, 3), "within_one": round(within1, 3), "spearman_rho": round(rho, 3)}


def assign(tasks: list[GoldenTask], cal: dict) -> None:
    for t in tasks:
        if t.eval_type == "flag_match":
            continue
        t.metadata["complexity_score"] = round(complexity_score(t.patch_stats), 3)
        if t.difficulty_source in ("pending", "heuristic") or t.difficulty not in ORD:
            t.difficulty = INV[_bucket(t.metadata["complexity_score"], cal["t1"], cal["t2"])]
            t.difficulty_source = "calibrated_heuristic"


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    return ranks


def _spearman(a: list[float], b: list[float]) -> float:
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else 0.0
