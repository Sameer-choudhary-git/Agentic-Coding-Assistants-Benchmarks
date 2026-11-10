# Paper: Agentic Coding Assistants (IEEE conference, 6-page target)

| File | What it is |
|---|---|
| `main.tex` | The paper: all eight outline sections. Author block is a placeholder. |
| `literature-summary.md` | Summary of every paper on the reading list, with corrections to the outline. |
| `build_tables.py` | Writes `references.bib` and `tables/*.tex` from `../evidence/*.json`. Re-run after editing the evidence. |
| `tables/` | Generated tables (features, acceptance, benchmarks, pilot, AIDev). Do not edit by hand. |
| `IEEEtran.cls`, `IEEEtran.bst` | IEEE class (v1.8a) and bibliography style, bundled so the paper builds offline. |

Build (TeX Live or MiKTeX):

```
python paper/build_tables.py
cd paper && latexmk -pdf main.tex     # or: pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Overleaf: upload the `paper/` folder and compile `main.tex` with pdfLaTeX.

## What is still open

- **Authors and affiliations** in `main.tex`.
- **SWE-bench pilot** (`swebench_pilot/`). When `swebench_pilot/results.csv` exists, `build_tables.py` adds
  the pilot table and the methodology sentence switches from "pending" to "complete". Results must come
  from real runs; the paper reports none until then.
- **AIDev re-analysis** (`analysis/aidev/`). When `analysis/aidev/output/aidev_table.tex` exists it is
  copied to `tables/aidev.tex`. Add `\input{tables/aidev.tex}` in Section V-C if you want to show it.
- Product facts in Table I were checked on 9 Nov 2026. Re-check them before submission.
