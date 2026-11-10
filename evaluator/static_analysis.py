"""Ruff (code quality) and Semgrep (security) analysis of a submission versus its baseline.

Both tools only *read* source files; they never execute submitted code, so they run on the host
in every execution mode. A missing tool is reported as ``unavailable`` and never as zero findings.
"""

from __future__ import annotations

import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluator.paths import CONFIG_DIR
from evaluator.procs import find_tool, run, tool_version

RUFF_CONFIG = CONFIG_DIR / "ruff.toml"
SEMGREP_RULES = CONFIG_DIR / "semgrep" / "rules.yml"


def _python_files(root: Path) -> List[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py") if "_acb" not in p.relative_to(root).parts)


def _key_counter(findings: List[Dict[str, object]], fields: Tuple[str, ...]) -> Counter:
    return Counter(tuple(f.get(k) for k in fields) for f in findings)


def _new_findings(
    baseline: List[Dict[str, object]], submission: List[Dict[str, object]], fields: Tuple[str, ...]
) -> List[Dict[str, object]]:
    """Findings present in the submission but not in the baseline. Matching ignores line numbers,
    which shift when code is edited; a finding is "new" if its (file, rule, message) key occurs
    more often than in the baseline."""
    remaining = _key_counter(baseline, fields)
    new = []
    for finding in submission:
        key = tuple(finding.get(k) for k in fields)
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            new.append(finding)
    return new


# ----------------------------------------------------------------------------- Ruff


def _ruff_run(command: List[str], root: Path) -> Tuple[Optional[List[Dict[str, object]]], Optional[str], Dict[str, object]]:
    files = _python_files(root)
    if not files:
        return [], None, {"exit_code": 0}
    result = run(
        [*command, "check", "--config", str(RUFF_CONFIG), "--no-cache", "--output-format", "json", "--exit-zero", *files],
        cwd=root,
        timeout_s=120,
    )
    meta = result.to_dict()
    if result.exit_code != 0 or result.timed_out:
        return None, (result.stderr or result.stdout or "ruff failed").strip()[:2000], meta
    try:
        raw = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return None, f"cannot parse ruff output: {exc}", meta
    findings = []
    for item in raw:
        filename = item.get("filename") or ""
        try:
            rel = Path(filename).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = Path(filename).name
        code = item.get("code") or "syntax-error"
        findings.append(
            {
                "path": rel,
                "code": code,
                "category": "".join(ch for ch in code if ch.isalpha()) or code,
                "message": item.get("message"),
                "line": (item.get("location") or {}).get("row"),
            }
        )
    return findings, None, meta


def analyse_ruff(baseline_dir: Path, submission_dir: Path) -> Dict[str, object]:
    command = find_tool("ruff", "ACB_RUFF_BIN")
    if not command:
        return {
            "status": "unavailable",
            "available": False,
            "version": None,
            "error": "ruff not found (pip install ruff, or set ACB_RUFF_BIN)",
        }
    version = tool_version(command)
    base, base_err, _ = _ruff_run(command, baseline_dir)
    sub, sub_err, meta = _ruff_run(command, submission_dir)
    if base_err or sub_err or base is None or sub is None:
        return {"status": "error", "available": True, "version": version, "error": base_err or sub_err}
    fields = ("path", "code", "message")
    new = _new_findings(base, sub, fields)
    return {
        "status": "ran",
        "available": True,
        "version": version,
        "config": "evaluator/config/ruff.toml",
        "baseline_count": len(base),
        "submission_count": len(sub),
        "new_count": len(new),
        "by_category": dict(sorted(Counter(f["category"] for f in sub).items())),
        "new_by_category": dict(sorted(Counter(f["category"] for f in new).items())),
        "findings": sub,
        "new_findings": new,
        "duration_s": meta.get("duration_s"),
    }


# ----------------------------------------------------------------------------- Semgrep


def _semgrep_command() -> Tuple[Optional[List[str]], str]:
    local = find_tool("semgrep", "ACB_SEMGREP_BIN")
    if local:
        return local, "local"
    if os.environ.get("ACB_SEMGREP_DOCKER") == "1" and shutil.which("docker"):
        return [shutil.which("docker") or "docker"], "docker"
    return None, "none"


def _semgrep_configs() -> List[str]:
    configs = [str(SEMGREP_RULES)]
    extra = os.environ.get("ACB_SEMGREP_EXTRA_CONFIGS", "").strip()
    if extra:
        configs += [c.strip() for c in extra.split(",") if c.strip()]
    return configs


def _semgrep_run(command: List[str], how: str, root: Path) -> Tuple[Optional[List[Dict[str, object]]], Optional[str]]:
    files = _python_files(root)
    if not files:
        return [], None
    if how == "docker":
        image = os.environ.get("ACB_SEMGREP_IMAGE", "semgrep/semgrep:latest")
        args = [
            *command,
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{root.resolve()}:/src:ro",
            "-v",
            f"{SEMGREP_RULES.parent.resolve()}:/rules:ro",
            "-w",
            "/src",
            image,
            "semgrep",
            "scan",
            "--config",
            "/rules/rules.yml",
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--quiet",
            *files,
        ]
    else:
        args = [*command, "scan"]
        for config in _semgrep_configs():
            args += ["--config", config]
        args += ["--json", "--metrics=off", "--disable-version-check", "--quiet", *files]
    result = run(args, cwd=root, timeout_s=300)
    if result.timed_out:
        return None, "semgrep timed out"
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None, (result.stderr or "cannot parse semgrep output").strip()[:2000]
    if result.exit_code not in (0, 1) and not data.get("results"):
        return None, (result.stderr or f"semgrep exited with {result.exit_code}").strip()[:2000]
    findings = []
    for item in data.get("results", []):
        extra = item.get("extra") or {}
        path = Path(item.get("path", ""))
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix() if path.is_absolute() else path.as_posix()
        except ValueError:
            rel = path.as_posix()
        findings.append(
            {
                "path": rel,
                "rule_id": str(item.get("check_id", "")).split(".")[-1],
                "severity": extra.get("severity"),
                "message": (extra.get("message") or "")[:500],
                "line": (item.get("start") or {}).get("line"),
            }
        )
    errors = data.get("errors") or []
    error_text = "; ".join(str(e.get("message", e))[:200] for e in errors[:5]) if errors else None
    return findings, error_text


def analyse_semgrep(baseline_dir: Path, submission_dir: Path) -> Dict[str, object]:
    command, how = _semgrep_command()
    if not command:
        return {
            "status": "unavailable",
            "available": False,
            "version": None,
            "error": "semgrep not found (install semgrep, set ACB_SEMGREP_BIN, or set ACB_SEMGREP_DOCKER=1)",
        }
    version = tool_version(command) if how == "local" else f"docker:{os.environ.get('ACB_SEMGREP_IMAGE', 'semgrep/semgrep:latest')}"
    base, base_err = _semgrep_run(command, how, baseline_dir)
    sub, sub_err = _semgrep_run(command, how, submission_dir)
    if base is None or sub is None:
        return {"status": "error", "available": True, "version": version, "error": base_err or sub_err}
    fields = ("path", "rule_id")
    new = _new_findings(base, sub, fields)
    resolved = _new_findings(sub, base, fields)
    return {
        "status": "ran",
        "available": True,
        "version": version,
        "runner": how,
        "configs": ["evaluator/config/semgrep/rules.yml"] + [c for c in _semgrep_configs()[1:]],
        "baseline_count": len(base),
        "submission_count": len(sub),
        "new_count": len(new),
        "resolved_count": len(resolved),
        "by_severity": dict(sorted(Counter(str(f["severity"]) for f in sub).items())),
        "findings": sub,
        "new_findings": new,
        "resolved_findings": resolved,
        "tool_warnings": sub_err or base_err,
    }
