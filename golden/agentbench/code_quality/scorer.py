"""Patch-level code-quality assessment (the "Code Quality Module").

For a patch against ``repo@base_commit`` we fetch each touched source file,
apply the patch in memory and compare *before* vs *after*:

  reliability      new lint findings (ruff; pyflakes-level defects weigh double)
  complexity       functions pushed over CCN 10, growth of the most complex function (lizard)
  maintainability  maintainability-index drop (radon, Python)
  security         new bandit findings + insecure-pattern detectors on added lines
  hygiene          debug statements, TODOs, commented-out code, lint suppressions, broad excepts
  size             patch bloat relative to the gold patch (when a reference is given)

Each dimension has a penalty cap; QualityScore = 100 - sum(penalties), and each
sub-score is 100 * (1 - penalty/cap). Weights are deliberately simple and
documented so results are auditable (see reports/RESEARCH_REPORT.md section 4).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from ..diffutil import FileDiff, apply_file_diff, is_doc_path, is_test_path, language_of, parse_diff
from . import analyzers as A
from .fetch import FileFetcher

CAPS = {"reliability": 25, "complexity": 20, "maintainability": 10, "security": 30, "hygiene": 10, "size": 5}
CCN_THRESHOLD = 10
ANALYZABLE = {"python", "javascript", "typescript", "go", "java", "rust", "cpp", "c", "csharp", "ruby",
              "php", "kotlin", "swift", "scala"}


_STRAY_NAME = re.compile(r"^(reproduce|repro|debug|scratch|tmp|temp|test|check|verify|run|demo|example|final)"
                         r"[_\-\w]*\.(py|js|ts|go|rs|java|rb|php|sh|c|cpp)$", re.I)


def is_stray_file(fd: FileDiff) -> bool:
    """Scratch artefacts agents create and forget to delete: new code files at the
    repository root with names like reproduce_issue.py / debug_x.py / test_fix.py."""
    return fd.is_new and "/" not in fd.path and bool(_STRAY_NAME.match(fd.path))


@dataclass
class FileReport:
    path: str
    language: str
    status: str  # analyzed | new_file | fetch_failed | apply_failed | skipped
    added_lines: int = 0
    removed_lines: int = 0
    ccn_before: int = 0
    ccn_after: int = 0
    new_complex_functions: list[str] = field(default_factory=list)
    max_ccn_increase: int = 0
    long_functions_added: int = 0
    mi_before: float | None = None
    mi_after: float | None = None
    lint_new: dict = field(default_factory=dict)
    bandit_new: dict = field(default_factory=dict)
    smells: dict = field(default_factory=dict)
    security_patterns: dict = field(default_factory=dict)


def _new_findings(before: Counter, after: Counter) -> dict:
    return {k: after[k] - before.get(k, 0) for k in after if after[k] > before.get(k, 0)}


class QualityAssessor:
    def __init__(self, fetcher: FileFetcher):
        self.fetcher = fetcher

    def assess(self, repo: str, base_commit: str, patch: str, reference_patch: str | None = None) -> dict:
        diffs = [f for f in parse_diff(patch) if not f.is_binary]
        stray = [f for f in diffs if is_stray_file(f)]
        diffs = [f for f in diffs if f not in stray]
        src = [f for f in diffs if not is_test_path(f.path) and not is_doc_path(f.path)]
        tests_touched = [f for f in diffs if is_test_path(f.path)]
        reports: list[FileReport] = []
        py_before: dict[str, str] = {}
        py_after: dict[str, str] = {}

        for fd in src:
            lang = language_of(fd.path)
            rep = FileReport(fd.path, lang, "skipped", len(fd.added), len(fd.removed))
            sm = A.diff_smells(fd.added, lang)
            rep.smells, rep.security_patterns = sm["smells"], sm["security_patterns"]
            reports.append(rep)
            if lang not in ANALYZABLE or fd.is_deleted:
                continue
            before = "" if fd.is_new else self.fetcher.get(repo, base_commit, fd.old_path or fd.path)
            if before is None:
                rep.status = "fetch_failed"
                continue
            try:
                after = apply_file_diff(before, fd)
            except ValueError:
                rep.status = "apply_failed"
                continue
            rep.status = "new_file" if fd.is_new else "analyzed"
            self._complexity(rep, fd.path, before, after)
            if lang == "python":
                rep.mi_before = A.radon_mi(before) if before else None
                rep.mi_after = A.radon_mi(after)
                if before:
                    py_before[fd.path] = before
                py_after[fd.path] = after

        # batch the subprocess-based Python analyzers
        if py_after:
            rb, ra = A.ruff_counts(py_before), A.ruff_counts(py_after)
            bb, ba = A.bandit_counts(py_before), A.bandit_counts(py_after)
            for rep in reports:
                if rep.path in py_after:
                    rep.lint_new = _new_findings(rb.get(rep.path, Counter()), ra[rep.path])
                    rep.bandit_new = _new_findings(bb.get(rep.path, Counter()), ba[rep.path])
                    # bandit already covers these for Python: avoid double counting
                    rep.security_patterns = {k: v for k, v in rep.security_patterns.items()
                                             if k in ("dom_xss_sink", "hardcoded_secret")}

        result = self._score(reports, diffs, tests_touched, reference_patch, stray)
        return result

    @staticmethod
    def _complexity(rep: FileReport, path: str, before: str, after: str) -> None:
        lb = A.lizard_metrics(path, before) if before else {"ok": True, "functions": {}, "total_ccn": 0}
        la = A.lizard_metrics(path, after)
        if not (lb.get("ok") and la.get("ok")):
            return
        rep.ccn_before, rep.ccn_after = lb["total_ccn"], la["total_ccn"]
        fb, fa = lb["functions"], la["functions"]
        max_inc = 0
        for name, m in fa.items():
            old = fb.get(name)
            if m["ccn"] > CCN_THRESHOLD and (old is None or old["ccn"] <= CCN_THRESHOLD):
                rep.new_complex_functions.append(f"{name} (CCN {m['ccn']})")
            if old is not None:
                max_inc = max(max_inc, m["ccn"] - old["ccn"])
            elif m["nloc"] > 60:
                rep.long_functions_added += 1
        rep.max_ccn_increase = max_inc

    @staticmethod
    def _score(reports: list[FileReport], diffs: list[FileDiff], tests_touched: list[FileDiff],
               reference_patch: str | None, stray: list[FileDiff] | None = None) -> dict:
        stray = stray or []
        P: dict[str, float] = {}
        lint_total = Counter()
        bandit_total = Counter()
        smell_total = Counter()
        secpat_total = Counter()
        for r in reports:
            lint_total.update(r.lint_new)
            bandit_total.update(r.bandit_new)
            smell_total.update(r.smells)
            secpat_total.update(r.security_patterns)
        severe = sum(v for k, v in lint_total.items() if A.SEVERE_RUFF.match(k))
        P["reliability"] = 3 * (sum(lint_total.values()) - severe) + 6 * severe
        n_complex = sum(len(r.new_complex_functions) for r in reports)
        worst_inc = max((r.max_ccn_increase for r in reports), default=0)
        P["complexity"] = 6 * n_complex + 1.5 * max(worst_inc - 3, 0) + 3 * sum(r.long_functions_added for r in reports)
        mi_pairs = [(r.mi_before - r.mi_after, r.mi_after) for r in reports
                    if r.mi_before is not None and r.mi_after is not None]
        mi_drops = [d for d, _ in mi_pairs]
        worst_mi = max(mi_drops, default=0.0)
        # MI is size-sensitive: a drop matters most once a file is no longer highly
        # maintainable (radon MI < 50); small edits to tiny files swing MI by several points.
        P["maintainability"] = max((1.5 * max(d - 1.0, 0.0) if after < 50 else 0.5 * max(d - 3.0, 0.0))
                                   for d, after in mi_pairs) if mi_pairs else 0.0
        P["security"] = 15 * sum(bandit_total.values()) + 10 * sum(secpat_total.values())
        P["hygiene"] = (3 * smell_total["debug_statement"] + 2 * smell_total["todo_marker"]
                        + 2 * smell_total["commented_out_code"] + 4 * smell_total["lint_suppression"]
                        + 4 * smell_total["broad_exception"] + 0.25 * smell_total["long_line"]
                        + 5 * len(stray))
        changed = sum(len(f.added) + len(f.removed) for f in diffs if not is_test_path(f.path))
        size_ratio = None
        if reference_patch:
            ref = sum(len(f.added) + len(f.removed) for f in parse_diff(reference_patch) if not is_test_path(f.path))
            if ref:
                size_ratio = round(changed / ref, 3)
                P["size"] = 2.5 * math.log2(size_ratio) if size_ratio > 2 else 0.0
        P.setdefault("size", 0.0)
        P = {k: round(min(v, CAPS[k]), 2) for k, v in P.items()}
        sub = {k: round(100 * (1 - P[k] / CAPS[k]), 1) for k in CAPS}
        analyzed = [r for r in reports if r.status in ("analyzed", "new_file")]
        return {
            "quality_score": round(max(0.0, 100 - sum(P.values())), 1),
            "subscores": sub,
            "penalties": P,
            "coverage": {"source_files": len(reports), "analyzed_files": len(analyzed),
                         "status": dict(Counter(r.status for r in reports))},
            "changed_source_lines": changed,
            "size_ratio_vs_reference": size_ratio,
            "tests_included": bool(tests_touched),
            "stray_files": [f.path for f in stray],
            "lint_new": dict(lint_total),
            "bandit_new": dict(bandit_total),
            "security_patterns": dict(secpat_total),
            "smells": dict(smell_total),
            "new_complex_functions": [f for r in reports for f in r.new_complex_functions],
            "ccn_delta": sum(r.ccn_after - r.ccn_before for r in analyzed),
            "mi_delta_worst": round(-worst_mi, 2) if mi_drops else None,
            "files": [r.__dict__ for r in reports],
        }
