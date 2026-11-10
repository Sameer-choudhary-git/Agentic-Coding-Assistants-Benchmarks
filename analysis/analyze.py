"""Reproducible analysis of exported experiment records.

Usage:
    python analysis/analyze.py --input artifacts/exports/<stamp>/results-<id>.csv --out analysis/output

Input is the normalised CSV (or the JSONL) exported by the platform. The script:

1. keeps only effective runs (latest run per planned attempt);
2. reports missing data (not started, in progress, operational failures, invalidated);
3. computes descriptive statistics on completed effective runs only (the documented denominator);
4. separately runs inferential tests on a *paired* subset (task × attempt blocks in which every
   assistant has a completed run), clearly labelled as exploratory;
5. writes CSV tables, PNG plots and a Markdown report.

With zero eligible records it writes an explicit empty-data message and no result tables.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

EMPTY_MESSAGE = (
    "No eligible experimental records were found (no effective run has completed evaluation). "
    "No descriptive statistics, tests or conclusions were produced."
)
BOOL_COLUMNS = ("is_effective_run", "eligible_for_success", "success", "evaluation_success", "timed_out", "regression_failure")


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple:
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    low = 0.0 if successes == 0 else max(0.0, (centre - margin) / denom)
    high = 1.0 if successes == n else min(1.0, (centre + margin) / denom)
    return (low, high)


def _to_bool(series: pd.Series) -> pd.Series:
    mapping = {"true": True, "false": False, "1": True, "0": False, "": None, "nan": None, "none": None}
    return series.map(lambda v: v if isinstance(v, bool) else mapping.get(str(v).strip().lower(), None))


def load(paths: List[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            frame = pd.DataFrame(rows)
        else:
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    if data.empty:
        return data
    data = data.drop_duplicates(subset=["run_id"])  # tolerate overlapping exports
    for col in BOOL_COLUMNS:
        if col in data.columns:
            data[col] = _to_bool(data[col].astype(str) if data[col].dtype != bool else data[col])
    for col in (
        "wall_clock_seconds",
        "iterations",
        "human_interventions",
        "ruff_new",
        "semgrep_new",
        "line_coverage",
        "mutation_score",
        "attempt_number",
        "run_number",
        "regression_failed",
    ):
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
    return data


def missing_data(effective: pd.DataFrame) -> pd.DataFrame:
    table = effective.pivot_table(index="assistant_id", columns="status", values="run_id", aggfunc="count", fill_value=0)
    table["effective_runs"] = table.sum(axis=1)
    return table.reset_index()


def describe(eligible: pd.DataFrame, by: List[str]) -> pd.DataFrame:
    rows = []
    for key, group in eligible.groupby(by):
        key = key if isinstance(key, tuple) else (key,)
        n = len(group)
        successes = int(group["success"].fillna(False).astype(bool).sum())
        low, high = wilson(successes, n)
        durations = group["wall_clock_seconds"].dropna()
        row = dict(zip(by, key))
        row.update(
            {
                "n_completed": n,
                "successes": successes,
                "success_rate": successes / n if n else math.nan,
                "wilson95_low": low,
                "wilson95_high": high,
                "timeouts": int(group["timed_out"].fillna(False).astype(bool).sum()),
                "regression_failures": int(group["regression_failure"].fillna(False).astype(bool).sum()),
                "duration_n": len(durations),
                "duration_median_s": durations.median() if len(durations) else math.nan,
                "duration_q1_s": durations.quantile(0.25) if len(durations) else math.nan,
                "duration_q3_s": durations.quantile(0.75) if len(durations) else math.nan,
                "iterations_mean": group["iterations"].mean(),
                "iterations_median": group["iterations"].median(),
                "interventions_mean": group["human_interventions"].mean(),
                "interventions_median": group["human_interventions"].median(),
                "ruff_new_mean": group.loc[group["ruff_status"] == "ran", "ruff_new"].mean(),
                "semgrep_runs": int((group["semgrep_status"] == "ran").sum()),
                "semgrep_new_total": group.loc[group["semgrep_status"] == "ran", "semgrep_new"].sum(),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def cochran_q(matrix: pd.DataFrame) -> Optional[Dict[str, float]]:
    """Cochran's Q for k related binary samples (rows = blocks, columns = assistants)."""
    from scipy.stats import chi2

    k = matrix.shape[1]
    if k < 2 or len(matrix) < 2:
        return None
    x = matrix.astype(int)
    col_totals = x.sum(axis=0)
    row_totals = x.sum(axis=1)
    total = row_totals.sum()
    denom = k * total - (row_totals**2).sum()
    if denom == 0:
        return {"q": 0.0, "df": k - 1, "p_value": 1.0, "blocks": int(len(x)), "note": "no variation within blocks"}
    q = (k - 1) * (k * (col_totals**2).sum() - total**2) / denom
    return {"q": float(q), "df": k - 1, "p_value": float(chi2.sf(q, k - 1)), "blocks": int(len(x))}


def mcnemar_exact(a: pd.Series, b: pd.Series) -> Dict[str, float]:
    from scipy.stats import binomtest

    b_only = int(((a == 1) & (b == 0)).sum())
    c_only = int(((a == 0) & (b == 1)).sum())
    n = b_only + c_only
    p = 1.0 if n == 0 else float(binomtest(b_only, n, 0.5).pvalue)
    return {"discordant_a_only": b_only, "discordant_b_only": c_only, "p_value": p}


def holm(pvalues: List[float]) -> List[float]:
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    m = len(pvalues)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


def inferential(eligible: pd.DataFrame) -> Dict[str, object]:
    """Paired, exploratory tests on complete task × attempt blocks."""
    result: Dict[str, object] = {
        "label": "Exploratory inferential analysis on complete paired blocks; small samples, interpret with caution.",
    }
    wide = eligible.pivot_table(index=["task_id", "attempt_number"], columns="assistant_id", values="success", aggfunc="first")
    complete = wide.dropna()
    result["assistants"] = list(complete.columns)
    result["complete_blocks"] = int(len(complete))
    if complete.shape[1] < 2 or len(complete) < 5:
        result["status"] = "skipped: fewer than 2 assistants or fewer than 5 complete paired blocks"
        return result
    binary = complete.astype(bool).astype(int)
    result["cochran_q"] = cochran_q(binary)
    pairs = list(itertools.combinations(binary.columns, 2))
    tests = [dict(a=a, b=b, **mcnemar_exact(binary[a], binary[b])) for a, b in pairs]
    for test, adj in zip(tests, holm([t["p_value"] for t in tests])):
        test["p_value_holm"] = adj
    result["pairwise_mcnemar_exact"] = tests
    durations = eligible.pivot_table(
        index=["task_id", "attempt_number"], columns="assistant_id", values="wall_clock_seconds", aggfunc="first"
    ).dropna()
    if durations.shape[1] >= 3 and len(durations) >= 5:
        from scipy.stats import friedmanchisquare

        stat, p = friedmanchisquare(*[durations[c] for c in durations.columns])
        result["friedman_duration"] = {"statistic": float(stat), "p_value": float(p), "blocks": int(len(durations))}
    result["status"] = "computed"
    return result


def plots(by_assistant: pd.DataFrame, eligible: pd.DataFrame, out: Path) -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = []
    fig, ax = plt.subplots(figsize=(7, 3.2))
    y = range(len(by_assistant))
    rates = by_assistant["success_rate"].fillna(0)
    ax.barh(list(y), rates, color="#1d5c8c", alpha=0.85)
    err_low = (by_assistant["success_rate"] - by_assistant["wilson95_low"]).fillna(0)
    err_high = (by_assistant["wilson95_high"] - by_assistant["success_rate"]).fillna(0)
    ax.errorbar(rates, list(y), xerr=[err_low, err_high], fmt="none", ecolor="#17212b", capsize=4)
    ax.set_yticks(list(y), [f"{a} (n={n})" for a, n in zip(by_assistant["assistant_id"], by_assistant["n_completed"])])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Success rate among completed effective runs (Wilson 95% CI)")
    fig.tight_layout()
    path = out / "success_by_assistant.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    files.append(path.name)

    groups = [(a, g["wall_clock_seconds"].dropna() / 60) for a, g in eligible.groupby("assistant_id")]
    groups = [(a, d) for a, d in groups if len(d)]
    if groups:
        fig, ax = plt.subplots(figsize=(7, 3.2))
        try:
            ax.boxplot([d for _, d in groups], orientation="horizontal")
        except TypeError:  # matplotlib < 3.10
            ax.boxplot([d for _, d in groups], vert=False)
        ax.set_yticks(range(1, len(groups) + 1), [f"{a} (n={len(d)})" for a, d in groups])
        ax.set_xlabel("Session duration (minutes)")
        fig.tight_layout()
        path = out / "duration_by_assistant.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        files.append(path.name)
    return files


def _md_table(frame: pd.DataFrame, float_cols: Optional[List[str]] = None) -> str:
    float_cols = float_cols or []
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in frame.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                cells.append("—" if math.isnan(v) else f"{v:.3f}" if c in float_cols else f"{v:.1f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run(inputs: List[Path], out: Path, benchmark: Optional[str] = None) -> Dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    data = load(inputs)
    if "task_benchmark" in data.columns:
        present = sorted(set(data["task_benchmark"].dropna()))
        if benchmark:
            data = data[data["task_benchmark"] == benchmark]
        elif len(present) > 1:
            raise SystemExit(
                f"The export mixes benchmarks ({', '.join(present)}). Run once per benchmark with --benchmark custom "
                "or --benchmark swebench_verified; the two are never pooled."
            )
    if data.empty or "is_effective_run" not in data.columns:
        (out / "REPORT.md").write_text(f"# Analysis report\n\n{EMPTY_MESSAGE}\n", encoding="utf-8")
        return {"status": "empty", "message": EMPTY_MESSAGE}
    effective = data[data["is_effective_run"] == True]  # noqa: E712 - nullable booleans
    eligible = effective[effective["eligible_for_success"] == True]  # noqa: E712
    missing = missing_data(effective) if len(effective) else pd.DataFrame()
    if not missing.empty:
        missing.to_csv(out / "missing_data.csv", index=False)
    modes = sorted(set(eligible.get("eval_mode", pd.Series(dtype=str)).dropna()))
    if eligible.empty:
        report = f"# Analysis report\n\n{EMPTY_MESSAGE}\n\n## Missing data\n\n{_md_table(missing) if not missing.empty else 'No runs.'}\n"
        (out / "REPORT.md").write_text(report, encoding="utf-8")
        return {"status": "empty", "message": EMPTY_MESSAGE}

    by_assistant = describe(eligible, ["assistant_id"])
    by_cell = describe(eligible, ["assistant_id", "task_category"])
    by_category = describe(eligible, ["task_category"])
    by_assistant.to_csv(out / "summary_by_assistant.csv", index=False)
    by_cell.to_csv(out / "summary_by_assistant_category.csv", index=False)
    by_category.to_csv(out / "summary_by_category.csv", index=False)
    tests = inferential(eligible)
    (out / "inferential_tests.json").write_text(json.dumps(tests, indent=2, default=float), encoding="utf-8")
    images = plots(by_assistant, eligible, out)

    rate_cols = ["success_rate", "wilson95_low", "wilson95_high"]
    report = [
        "# Analysis report",
        "",
        f"Input files: {', '.join(p.name for p in inputs)}. Effective runs: {len(effective)}. "
        f"Completed (eligible) runs: {len(eligible)}. Evaluation modes: {', '.join(modes) or 'unknown'}.",
        "",
        "Denominator: completed effective runs. Operational failures, invalidated and unfinished runs are excluded "
        "from rates and listed under missing data.",
        "",
        "## Descriptive statistics by assistant",
        "",
        _md_table(
            by_assistant[
                [
                    "assistant_id",
                    "n_completed",
                    "successes",
                    *rate_cols,
                    "duration_median_s",
                    "iterations_mean",
                    "interventions_mean",
                    "regression_failures",
                ]
            ],
            rate_cols,
        ),
        "",
        "## Descriptive statistics by assistant and category (exploratory; three tasks per category)",
        "",
        _md_table(by_cell[["assistant_id", "task_category", "n_completed", "successes", "success_rate"]], ["success_rate"]),
        "",
        "## Missing data (effective runs by status)",
        "",
        _md_table(missing),
        "",
        "## Inferential tests (separate, exploratory)",
        "",
        f"{tests['label']} Complete paired blocks: {tests['complete_blocks']}. Status: {tests['status']}.",
        "",
        "```json",
        json.dumps({k: v for k, v in tests.items() if k not in ("label",)}, indent=2, default=float),
        "```",
        "",
        "## Figures",
        "",
        *[f"![{name}]({name})" for name in images],
        "",
    ]
    if len(modes) > 1:
        report.insert(4, "**Warning:** results mix evaluation modes; compare with care.\n")
    (out / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    return {"status": "ok", "eligible": int(len(eligible)), "files": sorted(p.name for p in out.iterdir())}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", nargs="+", required=True, type=Path, help="exported results CSV or runs JSONL file(s)")
    parser.add_argument("--out", type=Path, default=Path("analysis/output"))
    parser.add_argument("--benchmark", choices=["custom", "swebench_verified"], help="analyse one benchmark from a mixed export")
    args = parser.parse_args(argv)
    for path in args.input:
        if not path.exists():
            print(f"input not found: {path}", file=sys.stderr)
            return 2
    result = run(args.input, args.out, args.benchmark)
    if result["status"] == "empty":
        print(result["message"])
    else:
        print(f"Analysed {result['eligible']} completed runs. Outputs in {args.out}: {', '.join(result['files'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
