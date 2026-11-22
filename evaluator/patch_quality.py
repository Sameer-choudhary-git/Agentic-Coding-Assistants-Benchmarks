"""Code quality of an assistant's patch on a SWE-bench / golden task.

Passing the hidden tests says the patch works; it does not say the patch is good code. This module scores the
patch with the golden dataset's Code Quality Module (``golden/agentbench/code_quality``), the same scorer that
gave every reference fix its ``gold_quality_score``, so an assistant's patch and the reference fix are measured
on one scale:

  reliability      new lint findings (ruff; pyflakes-level defects weigh double)
  complexity       functions pushed over cyclomatic complexity 10, growth of the most complex function (lizard)
  maintainability  maintainability-index drop (radon, Python)
  security         new bandit findings and insecure patterns on added lines
  hygiene          debug prints, TODOs, commented-out code, lint suppressions, broad excepts, stray scratch files
  size             patch bloat relative to the reference fix's size

QualityScore = 100 - capped penalties (100 = the patch adds no detectable problem). Only *new* problems count:
every touched file is read at the base commit from the workspace's own git history and compared before and
after the patch, so existing debt in the repository is not charged to the assistant. Nothing is executed and
no network is used. Test files and docs are left out of the source analysis (tests the assistant adds do not
count against it).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from evaluator.paths import REPO_ROOT

GOLDEN_DIR = REPO_ROOT / "golden"
MAX_FILE_BYTES = 400_000
INSTALL_HINT = "install the golden code-quality tools: pip install lizard radon bandit ruff"


class WorkspaceFetcher:
    """Reads a file as it was at a commit from the workspace's git history (``git show commit:path``)."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def get(self, repo: str, commit: str, path: str) -> Optional[str]:  # noqa: ARG002 (same interface as FileFetcher)
        try:
            proc = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=self.workspace, capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or len(proc.stdout) > MAX_FILE_BYTES:
            return None
        return proc.stdout.decode("utf-8", "replace")


def _assessor_class():
    if str(GOLDEN_DIR) not in sys.path:
        sys.path.insert(0, str(GOLDEN_DIR))
    from agentbench.code_quality.scorer import QualityAssessor  # noqa: PLC0415

    return QualityAssessor


def assess_patch(
    workspace: Path,
    base_commit: str,
    patch: str,
    repo: str = "",
    reference_lines: Optional[int] = None,
    gold_quality_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Score ``patch`` (a diff against ``base_commit``). Never raises: problems become ``status`` values."""
    if not patch.strip():
        return {"status": "not_applicable", "reason": "empty patch"}
    try:
        assessor = _assessor_class()(WorkspaceFetcher(workspace))
    except ImportError as exc:
        return {"status": "unavailable", "error": f"{INSTALL_HINT} ({exc})"}
    try:
        result = assessor.assess(repo, base_commit, patch, reference_lines=reference_lines)
    except Exception as exc:  # noqa: BLE001 - quality must never break scoring
        return {"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:500]}"}
    cov = result.get("coverage") or {}
    out: Dict[str, Any] = {
        "status": "ran",
        "scorer": "golden/agentbench/code_quality (same as gold_quality_score)",
        **result,
        "reference_changed_lines": reference_lines,
        "gold_quality_score": gold_quality_score,
        "delta_vs_gold": (round(result["quality_score"] - gold_quality_score, 1) if gold_quality_score is not None else None),
    }
    if cov.get("source_files") and not cov.get("analyzed_files"):
        # e.g. only unsupported file types: hygiene/security regexes still ran, but structure could not be measured
        out["note"] = "no touched source file could be analysed structurally; only line-level checks ran"
    return out
