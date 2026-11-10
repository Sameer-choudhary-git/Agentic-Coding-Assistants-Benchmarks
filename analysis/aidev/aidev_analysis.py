"""Task-stratified PR acceptance from the public AIDev dataset (outline Section V-B and V-C).

Mirrors the design of Pinna et al. (arXiv:2602.08915): acceptance = merged / closed, stratified by
agent and by task type, with Wilson 95% intervals and a chi-square test of agent differences within
each task type. It reads the AIDev parquet tables published by Li, Zhang and Hassan (MSR 2026,
arXiv:2602.09185; Hugging Face dataset ``hao-li/AIDev``).

Nothing here calls an AI service. Downloading AIDev is free and needs only network access to
Hugging Face, which is why this script runs on your machine, not in the build sandbox.

Usage
-----
    pip install pandas pyarrow scipy matplotlib huggingface_hub
    python analysis/aidev/aidev_analysis.py download --data-dir data/aidev
    python analysis/aidev/aidev_analysis.py analyze  --data-dir data/aidev --out analysis/aidev/output

The table and column names below match the AIDev release used by the MSR'26 papers. If a later
release renames them, override with ``--pr-table``/``--type-table`` or edit COLUMN_ALIASES.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

HF_REPO = "hao-li/AIDev"
DEFAULT_PR_TABLE = "pull_request.parquet"  # curated subset (repos with >100 stars)
DEFAULT_TYPE_TABLE = "pr_task_type.parquet"

# Canonical name -> accepted spellings in the parquet files.
COLUMN_ALIASES = {
    "id": ["id", "pr_id"],
    "agent": ["agent", "agent_name"],
    "state": ["state", "pr_state"],
    "merged_at": ["merged_at", "mergedAt"],
    "type": ["type", "task_type", "pr_type"],
}

AGENT_LABELS = {
    "openai_codex": "OpenAI Codex",
    "codex": "OpenAI Codex",
    "copilot": "GitHub Copilot",
    "github_copilot": "GitHub Copilot",
    "cursor": "Cursor",
    "claude_code": "Claude Code",
    "claude": "Claude Code",
    "devin": "Devin",
}
STUDY_AGENTS = ["OpenAI Codex", "GitHub Copilot", "Cursor", "Claude Code"]
MIN_CELL = 10  # cells with fewer closed PRs are reported but excluded from tests


def normalise_columns(df: pd.DataFrame, needed: list[str]) -> pd.DataFrame:
    rename = {}
    for canon in needed:
        for alias in COLUMN_ALIASES[canon]:
            if alias in df.columns:
                rename[alias] = canon
                break
        else:
            raise KeyError(f"column '{canon}' not found (tried {COLUMN_ALIASES[canon]}); columns are {list(df.columns)}")
    return df.rename(columns=rename)


def agent_label(raw: object) -> str:
    key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
    return AGENT_LABELS.get(key, str(raw))


def wilson(successes: int, n: int, z: float = 1.959964) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def load(data_dir: Path, pr_table: str, type_table: str) -> pd.DataFrame:
    prs = normalise_columns(pd.read_parquet(data_dir / pr_table), ["id", "agent", "state", "merged_at"])
    types = normalise_columns(pd.read_parquet(data_dir / type_table), ["id", "type"])
    return prepare(prs, types)


def prepare(prs: pd.DataFrame, types: pd.DataFrame) -> pd.DataFrame:
    """Closed PRs only, one row per PR, with agent label, task type and merged flag."""
    df = prs[["id", "agent", "state", "merged_at"]].merge(types[["id", "type"]].drop_duplicates("id"), on="id", how="left")
    df = df[df["state"].astype(str).str.lower() == "closed"].copy()
    df["agent"] = df["agent"].map(agent_label)
    df["type"] = df["type"].fillna("unclassified").astype(str).str.lower()
    df["merged"] = df["merged_at"].notna()
    return df[["id", "agent", "type", "merged"]]


@dataclass
class Cell:
    agent: str
    type: str
    n: int
    merged: int

    @property
    def rate(self) -> float | None:
        return self.merged / self.n if self.n else None


def acceptance_table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by, dropna=False)["merged"].agg(n="size", merged="sum").reset_index()
    g["rate"] = g["merged"] / g["n"]
    bounds = [wilson(int(m), int(n)) for m, n in zip(g["merged"], g["n"], strict=True)]
    g["ci_low"] = [b[0] for b in bounds]
    g["ci_high"] = [b[1] for b in bounds]
    return g.sort_values(by).reset_index(drop=True)


def chi_square_by_type(df: pd.DataFrame, agents: list[str]) -> pd.DataFrame:
    """Agent x {merged, not merged} chi-square within each task type, cells with n >= MIN_CELL."""
    try:
        from scipy.stats import chi2_contingency
    except ImportError:  # pragma: no cover - scipy is in requirements.txt
        return pd.DataFrame(columns=["type", "agents", "chi2", "dof", "p_value"])
    rows = []
    sub = df[df["agent"].isin(agents)]
    for task_type, part in sub.groupby("type"):
        counts = part.groupby("agent")["merged"].agg(["size", "sum"])
        counts = counts[counts["size"] >= MIN_CELL]
        if len(counts) < 2:
            continue
        table = [[int(s), int(n - s)] for n, s in zip(counts["size"], counts["sum"], strict=True)]
        if any(sum(col) == 0 for col in zip(*table, strict=True)):
            continue  # all merged or none merged: test undefined
        chi2, p, dof, _ = chi2_contingency(table)
        rows.append({"type": task_type, "agents": len(counts), "chi2": chi2, "dof": dof, "p_value": p})
    out = pd.DataFrame(rows, columns=["type", "agents", "chi2", "dof", "p_value"])
    if len(out):  # Holm correction across task types
        order = out["p_value"].sort_values().index
        m = len(out)
        adj, running = {}, 0.0
        for rank, idx in enumerate(order):
            running = max(running, min(1.0, (m - rank) * out.loc[idx, "p_value"]))
            adj[idx] = running
        out["p_holm"] = pd.Series(adj)
    return out


def to_latex(by_agent_type: pd.DataFrame, agents: list[str]) -> str:
    types = sorted(by_agent_type["type"].unique())
    lines = [
        "% Generated by analysis/aidev/aidev_analysis.py from the AIDev dataset. Do not edit by hand.",
        "\\begin{table}[t]",
        "\\caption{AIDev acceptance (merged/closed) by agent and task type; cells with $n<%d$ in grey}" % MIN_CELL,
        "\\label{tab:aidev}",
        "\\centering\\scriptsize",
        "\\begin{tabular}{@{}l" + "r" * len(agents) + "@{}}",
        "\\toprule",
        "Type & " + " & ".join(agents) + "\\\\",
        "\\midrule",
    ]
    for t in types:
        cells = []
        for a in agents:
            row = by_agent_type[(by_agent_type["agent"] == a) & (by_agent_type["type"] == t)]
            if row.empty:
                cells.append("--")
                continue
            n, rate = int(row["n"].iloc[0]), float(row["rate"].iloc[0])
            txt = f"{100 * rate:.1f}"
            cells.append(txt if n >= MIN_CELL else f"\\textcolor{{gray}}{{{txt}}}")
        lines.append(t.replace("_", "\\_") + " & " + " & ".join(cells) + "\\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def plot(by_agent_type: pd.DataFrame, agents: list[str], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = by_agent_type[by_agent_type["agent"].isin(agents) & (by_agent_type["n"] >= MIN_CELL)]
    pivot = data.pivot(index="type", columns="agent", values="rate").reindex(columns=agents)
    fig, ax = plt.subplots(figsize=(7, 3.2))
    im = ax.imshow(pivot.values * 100, aspect="auto", cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, fontsize=8)
    ax.set_yticks(range(len(pivot.index)), pivot.index, fontsize=8)
    for (i, j), v in pd.DataFrame(pivot.values).stack().items():
        ax.text(j, i, f"{100 * v:.0f}", ha="center", va="center", fontsize=7, color="white" if v > 0.6 else "black")
    fig.colorbar(im, ax=ax, label="Accepted (%)")
    ax.set_title(f"AIDev acceptance by agent and task type (cells n ≥ {MIN_CELL})", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def analyze(df: pd.DataFrame, out: Path, agents: list[str] = STUDY_AGENTS) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    by_agent = acceptance_table(df, ["agent"])
    by_type = acceptance_table(df, ["type"])
    by_agent_type = acceptance_table(df, ["agent", "type"])
    tests = chi_square_by_type(df, agents)
    by_agent.to_csv(out / "acceptance_by_agent.csv", index=False)
    by_type.to_csv(out / "acceptance_by_type.csv", index=False)
    by_agent_type.to_csv(out / "acceptance_by_agent_type.csv", index=False)
    tests.to_csv(out / "chi_square_by_type.csv", index=False)
    (out / "aidev_table.tex").write_text(to_latex(by_agent_type, agents), encoding="utf-8")
    plot(by_agent_type, agents, out / "aidev_heatmap.png")
    eligible = by_type[by_type["n"] >= MIN_CELL]
    gap = None
    if len(eligible) >= 2:
        hi, lo = eligible.loc[eligible["rate"].idxmax()], eligible.loc[eligible["rate"].idxmin()]
        gap = {"high": hi["type"], "low": lo["type"], "pp": round(100 * (hi["rate"] - lo["rate"]), 1)}
    summary = {
        "closed_prs": int(len(df)),
        "agents": by_agent.set_index("agent")[["n", "rate"]].round(4).to_dict("index"),
        "largest_task_type_gap": gap,
        "note": "Secondary analysis of the public AIDev dataset. Acceptance = merged/closed PRs.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def download(data_dir: Path, tables: list[str]) -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        sys.exit("Install huggingface_hub first: pip install huggingface_hub")
    data_dir.mkdir(parents=True, exist_ok=True)
    for t in tables:
        path = hf_hub_download(HF_REPO, t, repo_type="dataset", local_dir=data_dir)
        print(f"downloaded {path}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="fetch AIDev tables from Hugging Face (free)")
    d.add_argument("--data-dir", type=Path, default=Path("data/aidev"))
    d.add_argument("--tables", nargs="+", default=[DEFAULT_PR_TABLE, DEFAULT_TYPE_TABLE])
    a = sub.add_parser("analyze", help="compute acceptance tables, tests, LaTeX and figure")
    a.add_argument("--data-dir", type=Path, default=Path("data/aidev"))
    a.add_argument("--out", type=Path, default=Path("analysis/aidev/output"))
    a.add_argument("--pr-table", default=DEFAULT_PR_TABLE)
    a.add_argument("--type-table", default=DEFAULT_TYPE_TABLE)
    args = ap.parse_args(argv)
    if args.cmd == "download":
        download(args.data_dir, args.tables)
        return 0
    df = load(args.data_dir, args.pr_table, args.type_table)
    print(json.dumps(analyze(df, args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
