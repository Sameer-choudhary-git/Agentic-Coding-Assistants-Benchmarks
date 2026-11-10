# Research limitations

State these limitations in the report and paper.

## Benchmark

* **Synthetic, project-specific suite.** 18 small Python tasks written for this study. It is not
  SWE-bench, is not a validated general-purpose benchmark, and results do not generalise to
  real-world repositories, other languages or larger codebases.
* **Three tasks per category.** Category-level differences are exploratory; one task can dominate a
  category. Difficulty labels are the authors' judgement (rationale recorded per task), not
  empirically calibrated.
* **Hidden tests define correctness.** A correct but differently-designed solution can fail a
  structural refactoring check, and tests cannot prove the absence of bugs. Prompts state the
  required structure explicitly to limit this.
* **Test-writing tasks** are judged by coverage and mutation score against a fixed mutant set
  (8–11 mutants). Mutants approximate realistic faults; a suite that reads the module's source to
  detect any change could game mutation testing. The evaluator flags such suites for manual review
  but does not fail them automatically.
* **Contamination.** Tasks are new, but the bug patterns are common; assistants may have seen similar
  code. The reference solutions are in the repository; keep it private until the study ends.

## Measurement

* **Small sample.** 36 attempts per assistant; confidence intervals are wide. Two attempts per pair
  barely capture run-to-run variability.
* **Human-operated workflow.** Iterations, interventions and durations depend on the operator. The
  protocol fixes definitions, but operator effects remain; record the operator and randomise order.
* **Products, not models.** Each assistant bundles a model, tools, context retrieval and UI; results
  cannot be attributed to any single component, and vendors update products during the study.
* **Static analysis.** Ruff and the custom Semgrep rules detect only specific patterns; zero findings
  do not mean secure or maintainable code. If Semgrep is unavailable, security metrics are missing,
  not zero.
* **Inferential statistics** in `analysis/analyze.py` (Cochran's Q, exact McNemar with Holm
  correction, Friedman) assume paired blocks and are exploratory; no significance claims should be
  made from descriptive dashboards.

## Platform and security

* **Local evaluation mode** runs submitted code on the host without filesystem or network
  isolation. Use Docker mode for the official study; record the mode.
* **Same-process gaming.** Submitted code runs in the same Python process as pytest. Deliberately
  malicious code could tamper with test reporting; diffs and logs should be reviewed for
  suspicious changes (harness-sensitive files are removed and flagged).
* **Agent filesystem access.** Workspaces live outside the repository, but an agent with unrestricted
  shell access could still search the disk for the repository. Prefer agents' workspace-restricted
  modes and keep the repository on a different drive or folder from the workspaces.
* **No authentication.** The web app is for trusted local use only.
* **Headless adapters** were not exercised against the real products in the build environment
  (see `assistant-integrations.md`).
