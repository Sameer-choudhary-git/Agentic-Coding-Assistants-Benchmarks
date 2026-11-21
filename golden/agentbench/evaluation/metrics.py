"""Statistics for stratified agent evaluation."""
from __future__ import annotations

import math
import random

from ..diffutil import is_test_path, parse_diff


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Proportion with Wilson score 95% interval (robust for small strata)."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def source_files(patch: str) -> set[str]:
    return {f.path for f in parse_diff(patch) if not is_test_path(f.path)}


def localization(pred_patch: str, gold_patch: str) -> dict:
    """File-level localisation precision/recall/F1 of the agent patch vs gold."""
    p, g = source_files(pred_patch), source_files(gold_patch)
    if not p or not g:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "extra_files": len(p - g)}
    tp = len(p & g)
    prec, rec = tp / len(p), tp / len(g)
    f1 = 2 * prec * rec / (prec + rec) if tp else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "extra_files": len(p - g)}


def paired_bootstrap(a: list[int], b: list[int], iters: int = 5000, seed: int = 0) -> tuple[float, float, float]:
    """Mean difference a-b over paired binary outcomes with 95% bootstrap CI."""
    rng = random.Random(seed)
    n = len(a)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    diffs = [x - y for x, y in zip(a, b)]
    obs = sum(diffs) / n
    boots = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(iters))
    return obs, boots[int(0.025 * iters)], boots[int(0.975 * iters)]


def cramers_v_domain_effect(table: dict[str, tuple[int, int]]) -> float:
    """Effect size of domain on success (chi-square based Cramér's V for a k x 2 table).
    table: domain -> (successes, n)."""
    rows = [(k, n - k) for k, n in table.values() if n]
    tot = sum(a + b for a, b in rows)
    if tot == 0 or len(rows) < 2:
        return float("nan")
    col = [sum(r[0] for r in rows), sum(r[1] for r in rows)]
    chi = 0.0
    for a, b in rows:
        rs = a + b
        for obs, cs in ((a, col[0]), (b, col[1])):
            exp = rs * cs / tot
            if exp:
                chi += (obs - exp) ** 2 / exp
    return math.sqrt(chi / tot) if tot else float("nan")
