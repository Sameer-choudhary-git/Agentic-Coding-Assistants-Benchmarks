"""Final score table for the paper, from the app's results export.

    python golden/scripts/score_table.py --input artifacts/exports/<stamp>/results-<id>.csv --out analysis/score_table

Input: the normalised results CSV (Exports page or ``npm run export -- <experiment-id>``). Only effective runs that
completed evaluation count (``is_effective_run`` and ``eligible_for_success``), the same denominator as the app.
With several attempts per task, each attempt is one observation.

Writes ``score_table.md`` (all tables) and one CSV per table:

1. main         per assistant: completed runs, resolved, success rate [Wilson 95% CI], domain-balanced success
                [stratified bootstrap 95% CI], mean QualityScore (all and resolved patches), difference from the
                reference fix, regression failures
2. by_domain    resolved / completed per assistant and domain
3. quality      mean quality sub-scores per assistant
4. pairwise     each pair of assistants on the tasks both completed: exact McNemar test on resolved, Holm-corrected,
                and the mean paired QualityScore difference [bootstrap 95% CI]

No scipy needed. A fixed seed makes every interval reproducible.
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
from pathlib import Path

import pandas as pd

SEED = 20261121
BOOT = 5000
DIMS = ["reliability", "complexity", "maintainability", "security", "hygiene", "size"]
DOMAIN_LABEL = {
    "bug_fixing": "Bug fix",
    "feature_implementation": "Feature",
    "security_remediation": "Security fix",
    "refactoring": "Refactoring",
    "performance": "Performance",
    "frontend_visual": "Frontend/visual",
}


def to_bool(v) -> bool | None:
    return {"true": True, "1": True, "false": False, "0": False}.get(str(v).strip().lower())


def to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace("", None), errors="coerce")


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | tuple[None, None]:
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (0.0 if k == 0 else max(0.0, c - m)), (1.0 if k == n else min(1.0, c + m))


def domain_balanced(df: pd.DataFrame) -> float | None:
    rates = df.groupby("task_category")["resolved"].mean()
    return float(rates.mean()) if len(rates) else None


def boot_domain_balanced(df: pd.DataFrame, rng: random.Random) -> tuple[float, float] | tuple[None, None]:
    """Resample runs with replacement inside each domain, so every domain keeps its weight."""
    groups = [g["resolved"].tolist() for _, g in df.groupby("task_category")]
    if not groups:
        return None, None
    stats = []
    for _ in range(BOOT):
        stats.append(sum(sum(rng.choices(g, k=len(g))) / len(g) for g in groups) / len(groups))
    stats.sort()
    return stats[int(0.025 * BOOT)], stats[int(0.975 * BOOT) - 1]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2**n
    return min(1.0, 2 * tail)


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = running
    return out


def boot_mean(xs: list[float], rng: random.Random) -> tuple[float, float] | tuple[None, None]:
    if not xs:
        return None, None
    stats = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(BOOT))
    return stats[int(0.025 * BOOT)], stats[int(0.975 * BOOT) - 1]


def pct(x) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"


def num(x, d: int = 1) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in ("is_effective_run", "eligible_for_success", "success", "regression_failure"):
        if col in df:
            df[col] = df[col].map(to_bool)
    df = df[(df["is_effective_run"] == True) & (df["eligible_for_success"] == True)].copy()  # noqa: E712
    df["resolved"] = (df["success"] == True).astype(int)  # noqa: E712
    for col in ["quality_score", "quality_gold_score"] + [f"quality_{d}" for d in DIMS]:
        df[col] = to_num(df[col]) if col in df else float("nan")
    if "quality_status" in df:
        df.loc[df["quality_status"] != "ran", ["quality_score", "quality_gold_score"] + [f"quality_{d}" for d in DIMS]] = float("nan")
    df["unit"] = df["task_id"] + "#" + df.get("attempt_number", pd.Series("1", index=df.index)).astype(str)
    return df


def build(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rng = random.Random(SEED)
    main, quality = [], []
    for a, g in sorted(df.groupby("assistant_id"), key=lambda kv: kv[0]):
        k, n = int(g["resolved"].sum()), len(g)
        lo, hi = wilson(k, n)
        db = domain_balanced(g)
        dlo, dhi = boot_domain_balanced(g, rng)
        q = g["quality_score"].dropna()
        qr = g.loc[g["resolved"] == 1, "quality_score"].dropna()
        delta = (g["quality_score"] - g["quality_gold_score"]).dropna()
        reg = g["regression_failure"] if "regression_failure" in g else pd.Series(dtype=object)
        main.append({
            "assistant": a,
            "completed": n,
            "resolved": k,
            "success_rate": k / n if n else None, "success_ci_low": lo, "success_ci_high": hi,
            "domain_balanced": db, "domain_balanced_ci_low": dlo, "domain_balanced_ci_high": dhi,
            "domains": g["task_category"].nunique(),
            "quality_n": len(q), "quality_mean": q.mean() if len(q) else None,
            "quality_mean_resolved": qr.mean() if len(qr) else None, "quality_n_resolved": len(qr),
            "quality_delta_vs_reference": delta.mean() if len(delta) else None,
            "regression_failures": int((reg == True).sum()),  # noqa: E712
        })  # fmt: skip
        quality.append({"assistant": a, "n": len(q), **{d: g[f"quality_{d}"].dropna().mean() for d in DIMS}})

    by_domain = (
        df.groupby(["assistant_id", "task_category"])["resolved"].agg(["sum", "count"]).reset_index()
        .rename(columns={"assistant_id": "assistant", "task_category": "domain", "sum": "resolved", "count": "completed"})
    )  # fmt: skip
    by_domain["success_rate"] = by_domain["resolved"] / by_domain["completed"]

    pairs = []
    wide = df.pivot_table(index="unit", columns="assistant_id", values="resolved", aggfunc="first")
    qwide = df.pivot_table(index="unit", columns="assistant_id", values="quality_score", aggfunc="first")
    for a, b in itertools.combinations(sorted(df["assistant_id"].unique()), 2):
        both = wide[[a, b]].dropna()
        only_a = int(((both[a] == 1) & (both[b] == 0)).sum())
        only_b = int(((both[a] == 0) & (both[b] == 1)).sum())
        qd = (qwide[a] - qwide[b]).dropna().tolist() if a in qwide and b in qwide else []
        qlo, qhi = boot_mean(qd, rng)
        pairs.append({
            "assistant_a": a, "assistant_b": b, "paired_runs": len(both),
            "a_rate": both[a].mean() if len(both) else None, "b_rate": both[b].mean() if len(both) else None,
            "only_a_resolved": only_a, "only_b_resolved": only_b, "mcnemar_p": mcnemar_exact(only_a, only_b),
            "quality_pairs": len(qd), "quality_diff_mean": sum(qd) / len(qd) if qd else None,
            "quality_diff_ci_low": qlo, "quality_diff_ci_high": qhi,
        })  # fmt: skip
    pw = pd.DataFrame(pairs)
    if len(pw):
        pw["mcnemar_p_holm"] = holm(pw["mcnemar_p"].tolist())
    return {"main": pd.DataFrame(main), "by_domain": by_domain, "quality": pd.DataFrame(quality), "pairwise": pw}


def markdown(t: dict[str, pd.DataFrame], source: str) -> str:
    L = [f"# Score table\n\nSource: `{source}`. Completed effective runs only; seed {SEED}, {BOOT} bootstrap samples.\n"]
    L += ["## 1. Main results\n",
          "| Assistant | Completed | Resolved | Success [95% CI] | Domain-balanced [95% CI] | Quality (all) | Quality (resolved) | vs reference | Regressions |",
          "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in t["main"].to_dict("records"):
        L.append(
            f"| {r['assistant']} | {r['completed']} | {r['resolved']} | {pct(r['success_rate'])} [{pct(r['success_ci_low'])}, "
            f"{pct(r['success_ci_high'])}] | {pct(r['domain_balanced'])} [{pct(r['domain_balanced_ci_low'])}, "
            f"{pct(r['domain_balanced_ci_high'])}] | {num(r['quality_mean'])} | {num(r['quality_mean_resolved'])} "
            f"(n={r['quality_n_resolved']}) | {'—' if r['quality_delta_vs_reference'] is None else f'{r['quality_delta_vs_reference']:+.1f}'} "
            f"| {r['regression_failures']} |"
        )
    doms = sorted(t["by_domain"]["domain"].unique()) if len(t["by_domain"]) else []
    L += ["\n## 2. Success by domain (resolved / completed)\n",
          "| Assistant | " + " | ".join(DOMAIN_LABEL.get(d, d) for d in doms) + " |",
          "|---|" + "---|" * len(doms)]  # fmt: skip
    for a, g in t["by_domain"].groupby("assistant"):
        cells = {r["domain"]: f"{r['resolved']}/{r['completed']}" for r in g.to_dict("records")}
        L.append(f"| {a} | " + " | ".join(cells.get(d, "—") for d in doms) + " |")
    L += ["\n## 3. Code quality sub-scores (mean, 0–100)\n", "| Assistant | n | " + " | ".join(d.capitalize() for d in DIMS) + " |",
          "|---|---|" + "---|" * len(DIMS)]  # fmt: skip
    for r in t["quality"].to_dict("records"):
        L.append(f"| {r['assistant']} | {r['n']} | " + " | ".join(num(r[d], 0) for d in DIMS) + " |")
    L += ["\n## 4. Pairwise comparisons (paired on the same task and attempt)\n",
          "| A | B | Paired | A rate | B rate | Only A | Only B | McNemar p (Holm) | Quality A−B [95% CI] |",
          "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for r in t["pairwise"].to_dict("records"):
        qd = "—" if r["quality_diff_mean"] is None else f"{r['quality_diff_mean']:+.1f} [{num(r['quality_diff_ci_low'])}, {num(r['quality_diff_ci_high'])}]"
        L.append(
            f"| {r['assistant_a']} | {r['assistant_b']} | {r['paired_runs']} | {pct(r['a_rate'])} | {pct(r['b_rate'])} | "
            f"{r['only_a_resolved']} | {r['only_b_resolved']} | {r['mcnemar_p']:.3f} ({r['mcnemar_p_holm']:.3f}) | {qd} |"
        )
    L.append(
        "\nDomain-balanced success is the mean of the per-domain success rates, so a domain with more tasks does not "
        "dominate. With 5 tasks per domain, per-domain rates are very uncertain; report them as exploratory."
    )
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("analysis/score_table"))
    ap.add_argument("--benchmark", default="golden", help="task_benchmark to keep (default golden; 'all' keeps every row)")
    a = ap.parse_args()
    df = load(a.input)
    if a.benchmark != "all" and "task_benchmark" in df:
        df = df[df["task_benchmark"] == a.benchmark]
    a.out.mkdir(parents=True, exist_ok=True)
    if df.empty:
        (a.out / "score_table.md").write_text("# Score table\n\nNo completed runs in this export yet.\n", encoding="utf-8")
        print("no completed runs")
        return
    tables = build(df)
    for name, t in tables.items():
        t.to_csv(a.out / f"{name}.csv", index=False)
    (a.out / "score_table.md").write_text(markdown(tables, a.input.name), encoding="utf-8")
    print(a.out / "score_table.md")


if __name__ == "__main__":
    main()
