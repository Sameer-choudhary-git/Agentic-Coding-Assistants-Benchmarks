"""Minimal, dependency-free line-coverage plugin for pytest.

Loaded by the evaluator with ``-p acb_coverage``. It records which executable lines of the target
module(s) run while the test session executes and writes a JSON report.

Environment variables:
  ACB_COVERAGE_TARGETS  os.pathsep-separated paths (relative to the current directory)
  ACB_COVERAGE_OUT      path of the JSON report to write

Executable lines are those that carry bytecode in the compiled module (``co_lines``), which is the
same notion of "statement line" used by most coverage tools. Using one in-house implementation keeps
measurements identical across local and Docker evaluation modes.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import types

_targets = {}
_hits = {}
_resolved = {}


def _hits_for(filename):
    try:
        key = _resolved[filename]
    except KeyError:
        key = _resolved[filename] = os.path.realpath(filename) if filename and not filename.startswith("<") else None
    return _hits.get(key) if key else None


def _executable_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    code = compile(source, path, "exec")
    lines = set()
    stack = [code]
    while stack:
        current = stack.pop()
        for _start, _end, line in current.co_lines():
            if line is not None and line > 0:
                lines.add(line)
        stack.extend(c for c in current.co_consts if isinstance(c, types.CodeType))
    # Lines marked with "pragma: no cover" are excluded, as in coverage.py.
    source_lines = source.splitlines()
    return {n for n in lines if n <= len(source_lines) and "pragma: no cover" not in source_lines[n - 1]}


def _local_tracer(frame, event, arg):
    if event == "line":
        hits = _hits_for(frame.f_code.co_filename)
        if hits is not None:
            hits.add(frame.f_lineno)
    return _local_tracer


def _global_tracer(frame, event, arg):
    hits = _hits_for(frame.f_code.co_filename)
    if hits is not None:
        if event == "call":
            hits.add(frame.f_lineno)
        return _local_tracer
    return None


def pytest_configure(config):
    raw = os.environ.get("ACB_COVERAGE_TARGETS", "")
    for item in filter(None, raw.split(os.pathsep)):
        path = os.path.realpath(os.path.join(os.getcwd(), item))
        if os.path.isfile(path):
            _targets[path] = _executable_lines(path)
            _hits[path] = set()
    if _targets:
        threading.settrace(_global_tracer)
        sys.settrace(_global_tracer)


def pytest_unconfigure(config):
    sys.settrace(None)
    threading.settrace(None)
    out = os.environ.get("ACB_COVERAGE_OUT")
    if not out:
        return
    report = {"files": {}}
    total_exec = total_hit = 0
    for path, executable in _targets.items():
        hit = _hits[path] & executable
        rel = os.path.relpath(path, os.getcwd()).replace(os.sep, "/")
        report["files"][rel] = {
            "executable": len(executable),
            "covered": len(hit),
            "missing_lines": sorted(executable - hit),
        }
        total_exec += len(executable)
        total_hit += len(hit)
    report["line_coverage"] = (total_hit / total_exec) if total_exec else None
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
