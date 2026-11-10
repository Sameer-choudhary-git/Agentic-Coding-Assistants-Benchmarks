"""SWE-bench Verified: secondary analysis of the official leaderboard submissions (outline Section V-A).

Data: the public SWE-bench/experiments repository (https://github.com/SWE-bench/experiments), which holds
the per-instance results of every Verified leaderboard submission. Nothing here calls an AI service and
nothing costs money; it needs only `git` access to GitHub.

Two steps:

    # 1) build a compact snapshot from a (sparse) clone of SWE-bench/experiments
    git clone --filter=blob:none --no-checkout --depth 1 https://github.com/SWE-bench/experiments swex
    git -C swex sparse-checkout set --no-cone '/evaluation/verified/*/metadata.yaml' '/evaluation/verified/*/results/*.json'
    python analysis/swebench/verified_analysis.py snapshot --experiments swex --out analysis/swebench/data/verified_snapshot.json

    # 2) analyse the snapshot (works offline; the snapshot is committed to this repo)
    python analysis/swebench/verified_analysis.py analyze --snapshot analysis/swebench/data/verified_snapshot.json \
        --out analysis/swebench/output

What it computes:
  * trajectory  - best resolve rate reached by submission date
  * hardness    - per instance, the share of submissions that resolve it (empirical difficulty)
  * repository  - resolve rate by repository for the top submissions (task dependence on Verified)
  * issue year  - resolve rate by the year the issue was created (a contamination signal)
  * scaffold    - same model under different agents (how much the scaffold moves the score)
  * products    - whether any entry is one of the four studied products as shipped
  * pilot ids   - a seeded, hardness- and repository-stratified candidate sample for swebench_pilot/
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import subprocess
from collections import defaultdict
from pathlib import Path

N_VERIFIED = 500
PRODUCT_PATTERNS = {
    "GitHub Copilot": r"copilot",
    "Cursor": r"\bcursor\b",
    "Claude Code": r"claude[ _-]?code",
    "OpenAI Codex (product)": r"codex[ _-]?(cli|cloud|agent)|openai codex\b",
}


# ----------------------------------------------------------------------------------------- snapshot
def build_snapshot(experiments: Path) -> dict:
    import yaml  # only needed for this step

    root = experiments / "evaluation" / "verified"
    subs, all_ids, skipped = [], set(), []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        res, by_repo, by_time = (d / "results" / f for f in ("results.json", "resolved_by_repo.json", "resolved_by_time.json"))
        meta = yaml.safe_load((d / "metadata.yaml").read_text(encoding="utf-8")) if (d / "metadata.yaml").exists() else {}
        info, tags = (meta or {}).get("info") or {}, (meta or {}).get("tags") or {}
        label = {"folder": d.name, "name": info.get("name", d.name), "agent": tags.get("agent"), "model": tags.get("model")}
        if not res.exists() or not by_repo.exists():
            skipped.append({**label, "reason": "no results files"})
            continue
        r = json.loads(res.read_text(encoding="utf-8"))
        repo = json.loads(by_repo.read_text(encoding="utf-8"))
        if sum(v["total"] for v in repo.values()) != N_VERIFIED:
            skipped.append({**label, "reason": "per-repo totals are not the 500 Verified instances"})
            continue
        models = tags.get("model") or []
        subs.append(
            {
                "folder": d.name,
                "date": d.name[:8],
                "name": info.get("name", d.name),
                "model": models[0] if isinstance(models, list) and models else models or None,
                "model_org": tags.get("model_org"),
                "agent": tags.get("agent"),
                "org": tags.get("org"),
                "os_model": tags.get("os_model"),
                "os_system": tags.get("os_system"),
                "resolved": sorted(r.get("resolved", [])),
                "by_repo": repo,
                "by_time": json.loads(by_time.read_text(encoding="utf-8")) if by_time.exists() else {},
            }
        )
        for k in ("resolved", "no_generation", "no_logs"):
            all_ids |= set(r.get(k, []))
    try:
        commit = subprocess.run(
            ["git", "-C", str(experiments), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    ids = sorted(all_ids)
    index = {iid: i for i, iid in enumerate(ids)}
    for s in subs:  # store resolved instances as indices into `instances` to keep the file small
        s["resolved"] = [index[i] for i in s["resolved"]]
    return {
        "source": "https://github.com/SWE-bench/experiments",
        "commit": commit,
        "built": dt.date.today().isoformat(),
        "instances": ids,
        "submissions": subs,
        "skipped": skipped,
    }


# ------------------------------------------------------------------------------------------ analysis
def repo_of(instance_id: str) -> str:
    owner, rest = instance_id.split("__", 1)
    return f"{owner}/{rest.rsplit('-', 1)[0]}"


def rate(sub: dict) -> float:
    return len(sub["resolved"]) / N_VERIFIED


def trajectory(subs: list[dict]) -> list[dict]:
    best, out = 0.0, []
    for s in sorted(subs, key=lambda s: (s["date"], -rate(s))):
        if rate(s) > best:
            best = rate(s)
            out.append({"date": s["date"], "name": s["name"], "resolve_rate": round(best, 4)})
    return out


def hardness(snap: dict) -> list[dict]:
    subs = snap["submissions"]
    counts = [0] * len(snap["instances"])
    for s in subs:
        for i in s["resolved"]:
            counts[i] += 1
    return [
        {"instance_id": iid, "repo": repo_of(iid), "solved_by": c, "share": round(c / len(subs), 4)}
        for iid, c in zip(snap["instances"], counts, strict=True)
    ]


def hardness_bands(h: list[dict]) -> list[dict]:
    def band(share: float) -> str:
        if share == 0:
            return "never solved"
        if share < 0.10:
            return "under 10%"
        if share < 0.50:
            return "10-50%"
        if share < 0.90:
            return "50-90%"
        return "90% or more"

    labels = ["never solved", "under 10%", "10-50%", "50-90%", "90% or more"]
    counts = {k: 0 for k in labels}
    for x in h:
        counts[band(x["share"])] += 1
    return [{"band": k, "instances": counts[k]} for k in labels]


def top(subs: list[dict], k: int) -> list[dict]:
    return sorted(subs, key=lambda s: (-rate(s), s["date"]))[:k]


def by_repo(subs: list[dict], k: int) -> list[dict]:
    t = top(subs, k)
    repos = sorted(t[0]["by_repo"])
    out = []
    for r in repos:
        total = t[0]["by_repo"][r]["total"]
        mean = sum(s["by_repo"][r]["resolved"] for s in t) / (len(t) * total)
        out.append({"repo": r, "instances": total, "top_mean_rate": round(mean, 4)})
    return sorted(out, key=lambda x: -x["instances"])


def by_year(subs: list[dict], k: int) -> list[dict]:
    t = top(subs, k)
    years = sorted({y for s in t for y in s["by_time"]})
    out = []
    for y in years:
        tot = sum(s["by_time"].get(y, {}).get("total", 0) for s in t)
        res = sum(s["by_time"].get(y, {}).get("resolved", 0) for s in t)
        if tot:
            out.append({"year": y, "instances": tot // len(t), "top_mean_rate": round(res / tot, 4)})
    return out


def scaffold_spread(subs: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for s in subs:
        if s.get("model"):
            groups[s["model"]].append(s)
    out = []
    for m, g in groups.items():
        agents = {s.get("agent") or s["name"] for s in g}
        if len(agents) < 2:
            continue
        rates = [rate(s) for s in g]
        out.append(
            {
                "model": m,
                "submissions": len(g),
                "agents": len(agents),
                "min": round(min(rates), 4),
                "max": round(max(rates), 4),
                "spread_pp": round(100 * (max(rates) - min(rates)), 1),
            }
        )
    return sorted(out, key=lambda x: -x["spread_pp"])


def product_entries(entries: list[dict]) -> dict:
    """Search every Verified entry (analysed or skipped) for the four products as shipped."""
    found = {}
    for label, pat in PRODUCT_PATTERNS.items():
        found[label] = [e["name"] for e in entries if re.search(pat, f"{e['name']} {e.get('agent') or ''}", re.I)]
    codex_models = sorted({e["name"] for e in entries if re.search(r"codex", f"{e.get('model') or ''} {e['name']}", re.I)})
    return {"entries_searched": len(entries), "product_entries": found, "codex_branded_models_in_generic_scaffolds": codex_models}


def pilot_candidates(h: list[dict], n: int, seed: int) -> list[dict]:
    """Seeded sample: equal thirds from easy/medium/hard hardness tertiles (never-solved excluded),
    spreading picks across repositories inside each tertile."""
    rng = random.Random(seed)
    pool = sorted((x for x in h if x["solved_by"] > 0), key=lambda x: (-x["share"], x["instance_id"]))
    third = len(pool) // 3
    tiers = {"easy": pool[:third], "medium": pool[third : 2 * third], "hard": pool[2 * third :]}
    chosen = []
    per = [n // 3 + (1 if i < n % 3 else 0) for i in range(3)]
    for (tier, items), k in zip(tiers.items(), per, strict=True):
        items = items[:]
        rng.shuffle(items)
        used = defaultdict(int)
        picked = []
        while len(picked) < k and items:
            items.sort(key=lambda x: used[x["repo"]])
            x = items.pop(0)
            used[x["repo"]] += 1
            picked.append({**x, "tier": tier})
        chosen += picked
    return chosen


def latex_tables(res: dict) -> str:
    def pct(x: float) -> str:
        return f"{100 * x:.1f}"

    lines = [
        "% Generated by analysis/swebench/verified_analysis.py from SWE-bench/experiments @ " + (res["commit"] or "unknown")[:10],
        "\\begin{table}[t]",
        "\\caption{SWE-bench Verified leaderboard re-analysis (this study): %d submissions on all 500 instances}" % res["submissions"],
        "\\label{tab:swev}",
        "\\centering\\scriptsize",
        "\\begin{tabular}{@{}lr@{\\hspace{1.2em}}lr@{}}",
        "\\toprule",
        "\\multicolumn{2}{@{}l}{Instances by share of submissions resolving them} & \\multicolumn{2}{l@{}}{Top-%d mean rate by issue year} \\\\"  # noqa: E501
        % res["k"],
        "\\midrule",
    ]
    bands, years = res["hardness_bands"], res["by_year"]
    years = [y for y in years if y["instances"] >= 10]
    for i in range(max(len(bands), len(years))):
        esc = bands[i]["band"].replace("%", "\\%") if i < len(bands) else ""
        b = f"{esc} & {bands[i]['instances']}" if i < len(bands) else "&"
        y = f"{years[i]['year']} ($n$={years[i]['instances']}) & {pct(years[i]['top_mean_rate'])}\\%" if i < len(years) else "&"
        lines.append(f"{b} & {y}\\\\")
    lines += ["\\midrule", "\\multicolumn{4}{@{}l}{Top-%d mean rate by repository (largest five)}\\\\" % res["k"]]
    for r in res["by_repo"][:5]:
        lines.append(f"\\multicolumn{{3}}{{@{{}}l}}{{{r['repo']} ($n$={r['instances']})}} & {pct(r['top_mean_rate'])}\\%\\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def plot(res: dict, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.6))
    t = res["trajectory"]
    dates = [dt.datetime.strptime(x["date"], "%Y%m%d") for x in t]
    a.step(dates, [100 * x["resolve_rate"] for x in t], where="post", color="#1f5f99")
    a.scatter(dates, [100 * x["resolve_rate"] for x in t], s=8, color="#1f5f99")
    a.set_ylabel("Best resolved (%)", fontsize=8)
    a.set_title("Verified state of the art by submission date", fontsize=8)
    a.tick_params(labelsize=7)
    a.set_ylim(0, 100)
    import matplotlib.dates as mdates

    a.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    a.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    shares = [100 * x["share"] for x in res["hardness"]]
    b.hist(shares, bins=20, range=(0, 100), color="#7a9cc6", edgecolor="white")
    b.set_xlabel("Submissions resolving the instance (%)", fontsize=8)
    b.set_ylabel("Instances", fontsize=8)
    b.set_title("Empirical difficulty of the 500 instances", fontsize=8)
    b.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(out / "swebench_verified.pdf")
    fig.savefig(out / "swebench_verified.png", dpi=200)
    plt.close(fig)


def analyze(snap: dict, out: Path, k: int = 10, pilot_n: int = 12, seed: int = 2026) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    subs = snap["submissions"]
    h = hardness(snap)
    res = {
        "source": snap["source"],
        "commit": snap["commit"],
        "submissions": len(subs),
        "k": k,
        "date_range": [min(s["date"] for s in subs), max(s["date"] for s in subs)],
        "best": {"name": top(subs, 1)[0]["name"], "resolve_rate": round(rate(top(subs, 1)[0]), 4)},
        "median_resolve_rate": round(sorted(rate(s) for s in subs)[len(subs) // 2], 4),
        "trajectory": trajectory(subs),
        "hardness_bands": hardness_bands(h),
        "by_repo": by_repo(subs, k),
        "by_year": by_year(subs, k),
        "scaffold_spread": scaffold_spread(subs),
        "products": product_entries(subs + snap.get("skipped", [])),
        "pilot_candidates": pilot_candidates(h, pilot_n, seed),
        "pilot_seed": seed,
    }
    res["hardness"] = h
    (out / "summary.json").write_text(json.dumps({k2: v for k2, v in res.items() if k2 != "hardness"}, indent=2), encoding="utf-8")
    (out / "instance_hardness.csv").write_text(
        "instance_id,repo,solved_by,share\n" + "".join(f"{x['instance_id']},{x['repo']},{x['solved_by']},{x['share']}\n" for x in h),
        encoding="utf-8",
    )
    (out / "swebench_table.tex").write_text(latex_tables(res), encoding="utf-8")
    plot(res, out)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SWE-bench Verified leaderboard re-analysis")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--experiments", type=Path, required=True)
    s.add_argument("--out", type=Path, default=Path("analysis/swebench/data/verified_snapshot.json"))
    a = sub.add_parser("analyze")
    a.add_argument("--snapshot", type=Path, default=Path("analysis/swebench/data/verified_snapshot.json"))
    a.add_argument("--out", type=Path, default=Path("analysis/swebench/output"))
    a.add_argument("--top", type=int, default=10)
    a.add_argument("--pilot-n", type=int, default=12)
    a.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        snap = build_snapshot(args.experiments)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")
        print(f"{len(snap['submissions'])} submissions, {len(snap['instances'])} instances, {len(snap['skipped'])} skipped -> {args.out}")
        return 0
    res = analyze(json.loads(args.snapshot.read_text(encoding="utf-8")), args.out, args.top, args.pilot_n, args.seed)
    print(
        json.dumps(
            {k: res[k] for k in ("submissions", "date_range", "best", "median_resolve_rate", "hardness_bands", "products")}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
