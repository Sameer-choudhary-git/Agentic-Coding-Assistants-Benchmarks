# AgentBench-Golden

A multi-domain **golden dataset**, **code-quality module** and **automated evaluation
pipeline** for comparing agentic coding assistants (GitHub Copilot agent, Cursor, Claude
Code, Codex, SWE-agent, OpenHands, AutoCodeRover, …). Built for the paper outline
*"Agentic Coding Assistants: A Comparative Study of GitHub Copilot, Cursor, Claude Code
and Codex"* (Sections III and V).

| Deliverable | Where |
|---|---|
| Golden dataset (350 tasks, 8 domains) | `dataset/golden_v1.0.0.jsonl` (+ `.parquet`, `by_domain/`) |
| Datasheet (auto-generated) | `dataset/DATASHEET.md` |
| Human review sheet | `dataset/review_sheet.csv` |
| Build manifest (source SHA-256s, gate stats, calibration) | `dataset/manifest.json` |
| Evaluation results (auto-generated) | `reports/RESULTS.md`, `reports/results.json`, `reports/figures/` |
| Research write-up | `reports/RESEARCH_REPORT.md` |

## Domains

| Domain | Source(s) | Judged by |
|---|---|---|
| `bug_fix` | SWE-bench Verified, Multilingual, Pro, SWE-Bench++, SWE-rebench | FAIL_TO_PASS + PASS_TO_PASS tests |
| `feature_implementation` | SWE-bench Pro (`*_feat`), SWE-Bench++ (`feature-request`), classifier | tests |
| `refactoring` | SWE-bench Pro (`refactoring_enh`, `code_quality_enh`), classifier | tests (behaviour preserved) |
| `performance` | Pro, SWE-Bench++ (`performance-issue`), classifier | tests |
| `security_fix` | Pro (security labels/knowledge), classifier (CVE, injection, traversal, …) | tests |
| `frontend_visual` | SWE-bench Multimodal | tests |
| `test_generation` | derived from held-out Verified/Multilingual bug fixes (SWT-bench style) | tests fail on base, pass with hidden fix |
| `offensive_security_ctf` | NYU CTF Bench (the benchmark used by SWE-agent **EnIGMA**) | flag match |

SWE-bench+ (arXiv:2410.06992) is used in two ways: its instances are ingested as a
source, and its audit findings (solution leakage, weak tests) are turned into the
automatic **quality gates**.

## Pipeline

```
HF parquet ─► normalise (schema.py) ─► classify domain (taxonomy.py) ─► quality gates (gates.py)
   ─► difficulty calibration (difficulty.py) ─► anchored stratified sampling (sampler.py)
   ─► gold-patch quality profile (code_quality/) ─► export + datasheet + JSON-schema validation
   ─► evaluate agents (evaluation/) ─► report (tables + figures)
```

## Usage

```powershell
pip install -r requirements.txt
python -m agentbench all                      # build + evaluate published agents + report
python -m agentbench build --reuse-pool       # re-sample / re-profile without re-downloading
python -m agentbench evaluate --predictions my_agent.jsonl [--results resolved.json | --run-harness]
python -m agentbench quality --repo django/django --commit <sha> --patch fix.diff [--reference gold.diff]
pytest -q tests
```

Predictions use the SWE-bench format: one JSON object per line with `instance_id`
(or `task_id`), `model_patch` and `model_name_or_path`. Optionally add `resolved`, or
pass `--run-harness` to execute tests in Docker via the official `swebench` harness.

## Running the real tools

Run Claude Code, Codex, Cursor and Copilot through the main app (its assistant adapters and the
**Golden** benchmark in the Tasks page). The app scores patches with the SWE-bench harness. To score
any predictions file here, use `python -m agentbench evaluate --predictions preds.jsonl --run-harness`.

## Code Quality Module (`agentbench/code_quality`)

For any patch it fetches the touched files at `base_commit`, applies the patch in
memory, and compares **before vs after**:

| Dimension (cap) | Signal | Tool |
|---|---|---|
| reliability (25) | new lint findings; pyflakes-level defects weigh double | ruff |
| complexity (20) | functions pushed over CCN 10, growth of the most complex function, long new functions | lizard (15+ languages) |
| maintainability (10) | maintainability-index drop | radon |
| security (30) | new medium/high findings + insecure-pattern detectors (eval, shell=True, TLS off, innerHTML, secrets, SQL building, strcpy…) | bandit + regex |
| hygiene (10) | debug prints, TODOs, commented-out code, lint suppressions, broad excepts | regex, any language |
| size (5) | bloat relative to the gold patch | diff |

`QualityScore = 100 − Σ penalties`. *Quality-adjusted resolve rate* counts a task only
if it is resolved **and** QualityScore ≥ 80.

## Automation

* `python -m agentbench all`: a single command runs the whole pipeline and is deterministic (fixed seed, source hashes in the manifest).
* `.github/workflows/ci.yml` runs lint and the unit tests on every push.
* `.github/workflows/golden-refresh.yml` runs every week: it re-pulls the sources, rebuilds, re-evaluates, and opens a PR with the refreshed dataset and results.
* `run_pipeline.ps1` is the local Windows equivalent.
