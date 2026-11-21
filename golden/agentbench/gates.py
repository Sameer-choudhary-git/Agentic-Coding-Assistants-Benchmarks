"""Quality gates for golden-set admission.

Gates are inspired by the SWE-bench+ audit (Aleithan et al., arXiv:2410.06992),
which found that a large share of "resolved" SWE-bench instances were explained
by (a) the solution being leaked in the issue text and (b) weak tests. We
operationalise those findings as automatic, reproducible filters.

Each gate returns a flag string; tasks with any *blocking* flag are excluded.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .diffutil import is_doc_path, is_test_path, parse_diff
from .schema import GoldenTask

BLOCKING = {
    "no_gold_patch", "no_fail_to_pass", "problem_too_short", "problem_too_long",
    "patch_too_large", "too_many_files", "solution_leak", "tests_only_patch",
    "docs_only_patch", "test_patch_touches_source", "rebench_low_quality",
    "duplicate_instance", "near_duplicate", "patch_is_binary",
}
ADVISORY = {"possible_contamination", "weak_tests_single_f2p", "solution_hint_partial",
            "hints_contain_code", "url_only_problem"}

_TRIVIAL_LINE = re.compile(r"^[\s{}()\[\];,]*$|^\s*(#|//|\*|/\*)|^\s*(import |from \S+ import |return\s*$|pass\s*$|else:|try:|\})")


def solution_leak(problem: str, patch: str, min_chars: int, min_lines: int) -> tuple[int, int]:
    """Count non-trivial added patch lines that occur verbatim in the issue text.

    Returns (matching_lines, candidate_lines).
    """
    norm_problem = re.sub(r"\s+", " ", problem)
    cands = 0
    hits = 0
    for f in parse_diff(patch):
        if is_test_path(f.path):
            continue
        for line in f.added:
            s = line.strip()
            if len(s) < min_chars or _TRIVIAL_LINE.match(s):
                continue
            cands += 1
            if re.sub(r"\s+", " ", s) in norm_problem:
                hits += 1
    return hits, cands


def _shingles(text: str, k: int = 5) -> set[str]:
    toks = re.findall(r"\w+", text.lower())
    return {" ".join(toks[i:i + k]) for i in range(max(len(toks) - k + 1, 1))}


def apply_gates(tasks: list[GoldenTask], g: dict) -> dict:
    """Annotate ``task.gate_flags`` in place. Returns gate statistics."""
    stats: dict[str, Counter] = defaultdict(Counter)
    for t in tasks:
        flags = []
        code_task = t.eval_type == "fail_to_pass"
        n_chars = len(t.problem_statement.strip())
        if code_task:
            if not t.gold_patch.strip():
                flags.append("no_gold_patch")
            if not t.fail_to_pass:
                flags.append("no_fail_to_pass")
            if n_chars < g["min_problem_chars"]:
                flags.append("problem_too_short")
            if n_chars > g["max_problem_chars"]:
                flags.append("problem_too_long")
            ps = t.patch_stats
            if ps.get("changed", 0) > g["max_patch_changed_lines"]:
                flags.append("patch_too_large")
            if ps.get("files", 0) > g["max_patch_files"]:
                flags.append("too_many_files")
            files = parse_diff(t.gold_patch)
            if any(f.is_binary for f in files):
                flags.append("patch_is_binary")
            if files and all(is_test_path(f.path) for f in files):
                flags.append("tests_only_patch")
            elif files and all(is_doc_path(f.path) or is_test_path(f.path) for f in files):
                flags.append("docs_only_patch")
            tfiles = parse_diff(t.test_patch)
            if any(not is_test_path(f.path) and not is_doc_path(f.path)
                   and not f.path.endswith((".json", ".yaml", ".yml", ".txt", ".snap", ".png", ".svg"))
                   for f in tfiles):
                flags.append("test_patch_touches_source")
            hits, cands = solution_leak(t.problem_statement, t.gold_patch,
                                        g["leak_min_line_chars"], g["leak_min_matching_lines"])
            t.metadata["leak_lines"] = [hits, cands]
            if hits >= g["leak_min_matching_lines"] or (cands and hits == cands and hits >= 1):
                flags.append("solution_leak")
            elif hits:
                flags.append("solution_hint_partial")
            if len(t.fail_to_pass) == 1 and len(t.test_patch.splitlines()) < 15:
                flags.append("weak_tests_single_f2p")
            if re.search(r"```|\bdef \w+\(|diff --git", t.hints or ""):
                flags.append("hints_contain_code")
            if t.source == "swe_rebench":
                llm = t.metadata.get("llm_score", {})
                if llm.get("issue_text_score", 3) > g["rebench_max_issue_text_score"] or \
                   llm.get("test_score", 3) > g["rebench_max_test_score"]:
                    flags.append("rebench_low_quality")
        else:
            if n_chars < 80:
                flags.append("problem_too_short")
        if re.fullmatch(r"\s*(https?://\S+\s*)+", t.problem_statement or ""):
            flags.append("url_only_problem")
        if t.created_at and t.created_at < g["contamination_cutoff"]:
            flags.append("possible_contamination")
        t.gate_flags = flags

    # de-duplication: exact instance ids across sources, then near-duplicate issues
    seen: dict[str, GoldenTask] = {}
    prio = {s: i for i, s in enumerate(g.get("_source_priority", []))}
    for t in sorted(tasks, key=lambda x: prio.get(x.source, 99)):
        key = t.source_instance_id if t.eval_type != "flag_match" else t.task_id
        if key in seen:
            t.gate_flags.append("duplicate_instance")
            t.metadata["duplicate_of"] = seen[key].task_id
        else:
            seen[key] = t
    _near_dupes(tasks, g["near_duplicate_jaccard"], prio)

    for t in tasks:
        stats[t.source]["total"] += 1
        blocking = [f for f in t.gate_flags if f in BLOCKING]
        stats[t.source]["admitted" if not blocking else "rejected"] += 1
        for f in t.gate_flags:
            stats[t.source][f] += 1
    return {s: dict(c) for s, c in stats.items()}


def _near_dupes(tasks: list[GoldenTask], thresh: float, prio: dict) -> None:
    """MinHash-free near-duplicate detection, bucketed by repo for tractability."""
    by_repo: dict[str, list[GoldenTask]] = defaultdict(list)
    for t in tasks:
        if "duplicate_instance" not in t.gate_flags and t.repo:
            by_repo[t.repo.lower()].append(t)
    for group in by_repo.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda x: prio.get(x.source, 99))
        sh = [_shingles(t.problem_statement[:4000]) for t in group]
        for i in range(len(group)):
            if "near_duplicate" in group[i].gate_flags:
                continue
            for j in range(i + 1, len(group)):
                if "near_duplicate" in group[j].gate_flags:
                    continue
                a, b = sh[i], sh[j]
                if not a or not b:
                    continue
                jac = len(a & b) / len(a | b)
                if jac >= thresh:
                    group[j].gate_flags.append("near_duplicate")
                    group[j].metadata["duplicate_of"] = group[i].task_id


def is_admitted(t: GoldenTask) -> bool:
    return not any(f in BLOCKING for f in t.gate_flags)
