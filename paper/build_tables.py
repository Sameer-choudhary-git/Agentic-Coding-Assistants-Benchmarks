"""Generate the paper's references.bib and data tables from evidence/*.json (single source of truth).

    python paper/build_tables.py          # writes paper/references.bib and paper/tables/*.tex

If analysis/aidev/output/aidev_table.tex or swebench_pilot/results.csv exist (produced on your machine),
they are copied/converted into paper/tables/ as well; otherwise the paper shows a "pending" note.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
PAPER = ROOT / "paper"
TABLES = PAPER / "tables"

AGENT_ORDER = ["OpenAI Codex", "Claude Code", "Cursor", "GitHub Copilot"]


def tex(s: str) -> str:
    s = s.replace("\\", "\\textbackslash{}")
    s = re.sub(r"([&%$#_{}])", r"\\\1", s)
    return s.replace("~", "\\textasciitilde{}").replace(">=", "$\\geq$").replace(">", "$>$").replace("<", "$<$")


def bib_escape(s: str) -> str:
    return s.replace("&", "\\&").replace("%", "\\%").replace("_", "\\_")


def bibtex(src: dict) -> str:
    venue = src["venue"]
    fields = {
        "title": "{" + bib_escape(src["title"]) + "}",
        "author": " and ".join(a for a in src["authors"] if not a.startswith("et al"))
        + (" and others" if any(a.startswith("et al") for a in src["authors"]) else ""),
        "year": str(src["year"]),
    }
    if src.get("doi"):
        fields["doi"] = src["doi"]
    if src.get("arxiv"):
        fields["eprint"] = src["arxiv"]
        fields["archiveprefix"] = "arXiv"
    fields["url"] = src["url"]
    if venue.startswith("arXiv"):
        kind = "misc"
        fields["howpublished"] = f"arXiv:{src['arxiv']}" + (" (under review)" if "review" in venue else "")
    elif "blog" in venue.lower() or "GitHub" in venue:
        kind = "misc"
        fields["howpublished"] = bib_escape(venue)
    elif any(k in venue for k in ("Communications of the ACM", "Management Science", "Proc. ACM Meas")):
        kind = "article"
        fields["journal"] = bib_escape(venue)
    else:
        kind = "inproceedings"
        fields["booktitle"] = bib_escape(venue)
    body = ",\n".join(f"  {k} = {{{v}}}" if not v.startswith("{") else f"  {k} = {v}" for k, v in fields.items())
    return f"@{kind}{{{src['id']},\n{body}\n}}\n"


def features_table(feat: dict) -> str:
    rows = []
    for a in feat["assistants"]:
        rows.append(
            " & ".join(
                [
                    tex(a["name"]),
                    tex("; ".join(a["interactionModes"])),
                    tex("--".join([a["autonomy"][0], a["autonomy"][-1]]) if len(a["autonomy"]) > 1 else a["autonomy"][0]),
                    tex(a["context"]),
                    tex(a["tooling"]),
                    tex(a["execution"] + ". " + a["prOutput"]),
                ]
            )
            + "\\\\"
        )
    scale = "; ".join(f"{k}: {tex(v)}" for k, v in feat["autonomyScale"].items())
    return "\n".join(
        [
            f"% Generated from evidence/assistant_features.json (checked {feat['checkedOn']}). Do not edit by hand.",
            "\\begin{table*}[t]",
            "\\caption{Feature comparison of the four assistants (vendor documentation, checked " + feat["checkedOn"] + ")}",
            "\\label{tab:features}",
            "\\centering\\scriptsize",
            "\\begin{tabular}{@{}p{0.08\\textwidth}p{0.17\\textwidth}p{0.05\\textwidth}p{0.19\\textwidth}p{0.15\\textwidth}p{0.26\\textwidth}@{}}",  # noqa: E501
            "\\toprule",
            "Assistant & Interaction modes & Auton. & Context handling & Tooling & Execution and deployment\\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\multicolumn{6}{@{}p{0.95\\textwidth}@{}}{\\emph{Autonomy scale.} " + scale + "}\\\\",
            "\\end{tabular}",
            "\\end{table*}",
            "",
        ]
    )


def acceptance_table(items: list[dict]) -> str:
    studies = [
        ("li2025teammates", "Merge rate (AIDev-pop)", "Li et al.~\\cite{li2025teammates}, AIDev-pop"),
        ("rahman2026", "Mean acceptance across task types", "Rahman et al.~\\cite{rahman2026}, mean over types"),
        ("mazloomzadeh2026", "Estimated merge probability (GLMM)", "Mazloomzadeh et al.~\\cite{mazloomzadeh2026}, GLMM"),
    ]
    lines = [
        "% Generated from evidence/evidence.json. Do not edit by hand.",
        "\\begin{table}[t]",
        "\\caption{Reported PR acceptance (\\%) of the four assistants in three studies of AIDev data. Rank in parentheses.}",
        "\\label{tab:acceptance}",
        "\\centering\\scriptsize",
        "\\begin{tabular}{@{}p{0.36\\columnwidth}rrrr@{}}",
        "\\toprule",
        "Study & Codex & Claude C. & Cursor & Copilot\\\\",
        "\\midrule",
    ]
    for sid, metric, label in studies:
        vals = {}
        for i in items:
            if i["source"] == sid and i["metric"] == metric and i["subject"] in AGENT_ORDER:
                vals[i["subject"]] = i["value"]
        ranked = sorted(vals, key=lambda k: -vals[k])
        cells = [f"{vals[a]:g} ({ranked.index(a) + 1})" if a in vals else "--" for a in AGENT_ORDER]
        lines.append(label + " & " + " & ".join(cells) + "\\\\")
    human = next(i for i in items if i["source"] == "li2025teammates" and i["subject"] == "Human")
    lines += [
        "\\bottomrule",
        f"\\multicolumn{{5}}{{@{{}}p{{0.95\\columnwidth}}@{{}}}}{{Human PRs: {human['value']:g}\\% in AIDev-pop~\\cite{{li2025teammates}}; 84--86\\% per quarter in~\\cite{{mazloomzadeh2026}}.}}\\\\",  # noqa: E501
        "\\end{tabular}",
        "\\end{table}",
        "",
    ]
    return "\n".join(lines)


def benchmark_table(items: list[dict]) -> str:
    keep = [i for i in items if i["theme"] in ("benchmark", "benchmark_validity")]
    lines = [
        "% Generated from evidence/evidence.json. Do not edit by hand.",
        "\\begin{table}[t]",
        "\\caption{SWE-bench family: reported results and validity findings}",
        "\\label{tab:benchmarks}",
        "\\centering\\scriptsize",
        "\\begin{tabular}{@{}p{0.27\\columnwidth}p{0.42\\columnwidth}r@{\\ }l@{}}",
        "\\toprule",
        "System / set & Metric & \\multicolumn{2}{l}{Value}\\\\",
        "\\midrule",
    ]
    for i in keep:
        v = "--" if i["value"] is None else f"{i['value']:,g}"
        unit = "\\%" if i["unit"] == "%" else tex(i["unit"])
        lines.append(f"{tex(i['subject'])} & {tex(i['metric'])} & {v}{unit if i['unit'] == '%' else ''} & \\cite{{{i['source']}}}\\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(lines)


def pilot_table() -> str:
    res = ROOT / "swebench_pilot" / "results.csv"
    if not res.exists():
        return "% swebench_pilot/results.csv not found: pilot not yet run.\n\\renewcommand{\\pilotstatus}{pending, and no pilot results are reported here}%\n"  # noqa: E501
    rows = list(csv.DictReader(res.open(encoding="utf-8")))
    body = "\n".join(f"{tex(r['assistant'])} & {r['submitted']} & {r['resolved']} & {r['empty_patch']}\\\\" for r in rows)
    return (
        "\\renewcommand{\\pilotstatus}{complete (Table~\\ref{tab:pilot})}%\n\\begin{table}[t]\\caption{SWE-bench Verified pilot (this study)}\\label{tab:pilot}"  # noqa: E501
        "\\centering\\scriptsize\\begin{tabular}{@{}lrrr@{}}\\toprule Assistant & Submitted & Resolved & Empty\\\\\\midrule\n"
        + body
        + "\n\\bottomrule\\end{tabular}\\end{table}\n"
    )


def swebench_macros(r: dict) -> str:
    """Numbers quoted in the paper text, so prose and table cannot drift apart."""
    t = r["trajectory"]
    bands = {b["band"]: b["instances"] for b in r["hardness_bands"]}
    repos = r["by_repo"][:5]
    lo, hi = min(repos, key=lambda x: x["top_mean_rate"]), max(repos, key=lambda x: x["top_mean_rate"])
    sp = r["scaffold_spread"][0]
    pct = lambda x: f"{100 * x:.1f}"  # noqa: E731
    macros = {
        "swevSubs": str(r["submissions"]),
        "swevFirst": pct(t[0]["resolve_rate"]),
        "swevBest": pct(r["best"]["resolve_rate"]),
        "swevBestName": tex(r["best"]["name"]),
        "swevMedian": pct(r["median_resolve_rate"]),
        "swevNever": str(bands["never solved"]),
        "swevEasy": str(bands["90% or more"]),
        "swevRepoLo": f"{pct(lo['top_mean_rate'])}\\% ({tex(lo['repo'])})",
        "swevRepoHi": f"{pct(hi['top_mean_rate'])}\\% ({tex(hi['repo'])})",
        "swevSpreadModel": tex(sp["model"]),
        "swevSpreadMin": pct(sp["min"]),
        "swevSpreadMax": pct(sp["max"]),
        "swevSpreadAgents": str(sp["agents"]),
        "swevEntries": str(r["products"]["entries_searched"]),
    }
    return "% Generated by paper/build_tables.py from analysis/swebench/output/summary.json\n" + "".join(
        f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in macros.items()
    )


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    sources = json.loads((EVIDENCE / "sources.json").read_text(encoding="utf-8"))["sources"]
    items = json.loads((EVIDENCE / "evidence.json").read_text(encoding="utf-8"))["items"]
    feat = json.loads((EVIDENCE / "assistant_features.json").read_text(encoding="utf-8"))
    (PAPER / "references.bib").write_text(
        "% Generated from evidence/sources.json by paper/build_tables.py. Every entry was checked against its source.\n\n"
        + "\n".join(bibtex(s) for s in sources),
        encoding="utf-8",
    )
    (TABLES / "features.tex").write_text(features_table(feat), encoding="utf-8")
    (TABLES / "acceptance.tex").write_text(acceptance_table(items), encoding="utf-8")
    (TABLES / "benchmarks.tex").write_text(benchmark_table(items), encoding="utf-8")
    (TABLES / "pilot.tex").write_text(pilot_table(), encoding="utf-8")
    swe_out = ROOT / "analysis" / "swebench" / "output"
    if (swe_out / "swebench_table.tex").exists():
        shutil.copy(swe_out / "swebench_table.tex", TABLES / "swebench.tex")
        (PAPER / "figures").mkdir(exist_ok=True)
        shutil.copy(swe_out / "swebench_verified.pdf", PAPER / "figures" / "swebench_verified.pdf")
        summary = json.loads((swe_out / "summary.json").read_text(encoding="utf-8"))
        (TABLES / "swebench_numbers.tex").write_text(swebench_macros(summary), encoding="utf-8")
    aidev = ROOT / "analysis" / "aidev" / "output" / "aidev_table.tex"
    if aidev.exists():
        shutil.copy(aidev, TABLES / "aidev.tex")
    elif not (TABLES / "aidev.tex").exists():
        (TABLES / "aidev.tex").write_text("% AIDev re-analysis not yet run (analysis/aidev/aidev_analysis.py).\n", encoding="utf-8")
    print(f"wrote references.bib ({len(sources)} entries) and tables in {TABLES}")


if __name__ == "__main__":
    main()
