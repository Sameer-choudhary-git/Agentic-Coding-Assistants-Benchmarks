"""Static analyzers used by the code-quality module.

* lizard  - cyclomatic complexity / function size for 15+ languages
* radon   - maintainability index (Python)
* ruff    - lint findings (Python)  [subprocess, --isolated]
* bandit  - security findings (Python) [subprocess]
* regex   - language-agnostic diff smells and insecure-pattern detectors
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

import lizard
from radon.metrics import mi_visit

RUFF_SELECT = "E4,E7,E9,F,B,SIM,PLE,PLW,PLR0911,PLR0912,PLR0913,PLR0915,RUF005,RUF012,RUF015"
# pyflakes-level errors are real defects rather than style
SEVERE_RUFF = re.compile(r"^(F8|F6|F7|E9|PLE|B0(0[2-9]|1)|F401|F841)")


def lizard_metrics(path: str, code: str) -> dict:
    try:
        info = lizard.analyze_file.analyze_source_code(path, code)
    except Exception:  # noqa: BLE001
        return {"ok": False}
    funcs = {f.long_name: {"ccn": f.cyclomatic_complexity, "nloc": f.nloc, "params": len(f.parameters)}
             for f in info.function_list}
    return {"ok": True, "nloc": info.nloc, "functions": funcs,
            "total_ccn": sum(f["ccn"] for f in funcs.values())}


def radon_mi(code: str) -> float | None:
    try:
        return float(mi_visit(code, multi=True))
    except Exception:  # noqa: BLE001
        return None


def _tool(name: str) -> list[str] | None:
    exe = shutil.which(name)
    if exe:
        return [exe]
    return [sys.executable, "-m", name]


def ruff_counts(files: dict[str, str]) -> dict[str, Counter]:
    """files: relpath -> source. Returns relpath -> Counter(rule code)."""
    out = {p: Counter() for p in files}
    if not files:
        return out
    with tempfile.TemporaryDirectory() as d:
        mapping = _materialise(d, files)
        cmd = _tool("ruff") + ["check", "--isolated", "--no-cache", "--exit-zero", "--output-format", "json",
                               "--select", RUFF_SELECT, "--target-version", "py311", d]
        try:
            res = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
            for item in json.loads(res.stdout or "[]"):
                rel = mapping.get(os.path.normcase(os.path.abspath(item["filename"])))
                if rel is not None and item.get("code"):
                    out[rel][item["code"]] += 1
        except Exception:  # noqa: BLE001
            pass
    return out


def bandit_counts(files: dict[str, str]) -> dict[str, Counter]:
    """Medium/high severity findings by test id."""
    out = {p: Counter() for p in files}
    if not files:
        return out
    with tempfile.TemporaryDirectory() as d:
        mapping = _materialise(d, files)
        cmd = _tool("bandit") + ["-q", "-r", "-f", "json", "-ll", "-s", "B101", d]
        try:
            res = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=300)
            for item in json.loads(res.stdout or "{}").get("results", []):
                rel = mapping.get(os.path.normcase(os.path.abspath(item["filename"])))
                if rel is not None:
                    out[rel][item["test_id"]] += 1
        except Exception:  # noqa: BLE001
            pass
    return out


def _materialise(d: str, files: dict[str, str]) -> dict[str, str]:
    mapping = {}
    for i, (rel, code) in enumerate(files.items()):
        p = os.path.join(d, f"f{i}", os.path.basename(rel))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(code)
        mapping[os.path.normcase(os.path.abspath(p))] = rel
    return mapping


# ------------------------------------------------------------ diff smells
SMELLS: dict[str, list[re.Pattern]] = {
    "debug_statement": [re.compile(p) for p in (
        r"^\s*print\(", r"\bconsole\.(log|debug)\(", r"System\.(out|err)\.println\(", r"\bdbg!\(",
        r"\bpdb\.set_trace\(|\bbreakpoint\(\)", r"^\s*debugger;?", r"\bfmt\.Print(ln|f)?\(", r"\bvar_dump\(|\bdd\(")],
    "todo_marker": [re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")],
    "commented_out_code": [re.compile(r"^\s*(#|//)\s*(\w+\s*=[^=]|\w+\(.*\)\s*;?\s*$|return\b|if\s*\(|for\s*\(|def |import )")],
    "lint_suppression": [re.compile(p) for p in (
        r"#\s*(noqa|type:\s*ignore|pylint:\s*disable|nosec)", r"eslint-disable", r"@ts-(ignore|nocheck|expect-error)",
        r"@SuppressWarnings", r"//\s*nolint", r"#\[allow\(", r"#\s*pragma: no cover")],
    "broad_exception": [re.compile(p) for p in (
        r"^\s*except\s*:", r"^\s*except\s+(Base)?Exception\s*(as \w+)?\s*:\s*(pass)?\s*$",
        r"catch\s*\(\s*(Exception|Throwable|e|err|error)?\s*(\w+)?\s*\)\s*\{\s*\}", r"\.unwrap\(\)")],
}
SECURITY_PATTERNS: dict[str, re.Pattern] = {
    "eval_exec": re.compile(r"(?<![\w.])(eval|exec)\s*\("),
    "shell_injection": re.compile(r"shell\s*=\s*True|os\.system\(|child_process\.exec\(|Runtime\.getRuntime\(\)\.exec"),
    "unsafe_deserialization": re.compile(r"pickle\.loads?\(|yaml\.load\((?![^)]*Safe)|marshal\.loads|ObjectInputStream"),
    "weak_crypto": re.compile(r"\b(md5|sha1)\s*\(|hashlib\.(md5|sha1)\b|DES\b|MessageDigest\.getInstance\(\"(MD5|SHA-?1)"),
    "tls_verification_disabled": re.compile(r"verify\s*=\s*False|InsecureSkipVerify:\s*true|rejectUnauthorized:\s*false"),
    "dom_xss_sink": re.compile(r"\.innerHTML\s*=|dangerouslySetInnerHTML|document\.write\(|\$\(.*\)\.html\("),
    "hardcoded_secret": re.compile(r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
    "sql_string_building": re.compile(r"(?i)(execute|query)\s*\(\s*f?['\"](select|insert|update|delete)\b[^'\"]*(\{|['\"]\s*(\+|%))"),
    "unsafe_c_api": re.compile(r"\b(strcpy|strcat|sprintf|gets)\s*\("),
    "unsafe_block": re.compile(r"\bunsafe\s*\{"),
}


def diff_smells(added_lines: list[str], lang: str) -> dict:
    counts: Counter = Counter()
    sec: Counter = Counter()
    for line in added_lines:
        if len(line) > 120:
            counts["long_line"] += 1
        for name, pats in SMELLS.items():
            if name == "debug_statement" and lang == "go" and "fmt.Print" in line:
                continue
            if any(p.search(line) for p in pats):
                counts[name] += 1
        stripped = line.lstrip()
        if stripped.startswith(("#", "//", "*")):
            continue
        for name, pat in SECURITY_PATTERNS.items():
            if pat.search(line):
                sec[name] += 1
    return {"smells": dict(counts), "security_patterns": dict(sec)}
