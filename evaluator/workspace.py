"""Workspace creation, snapshotting, diffing and evaluation-directory preparation."""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from evaluator.paths import (
    HARNESS_SENSITIVE_FILES,
    IGNORED_DIRS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_BYTES,
    SUPPORT_DIR,
)
from evaluator.tasks import Task, iter_files


class WorkspaceError(Exception):
    """The submitted workspace cannot be evaluated (missing, too large, unreadable)."""


@dataclass
class Snapshot:
    files: Dict[str, bytes]
    ignored_dirs: List[str] = field(default_factory=list)

    def digest(self) -> str:
        h = hashlib.sha256()
        for rel in sorted(self.files):
            data = self.files[rel].replace(b"\r\n", b"\n")
            h.update(rel.encode("utf-8") + b"\0" + hashlib.sha256(data).hexdigest().encode("ascii") + b"\n")
        return h.hexdigest()


def create_workspace(task: Task, destination: Path) -> Path:
    """Copy the task's starter files into ``destination`` (which must be empty or absent)."""
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise WorkspaceError(f"destination is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    for path in iter_files(task.starter_dir):
        if path.name == ".gitkeep":
            target = destination / path.relative_to(task.starter_dir).parent
            target.mkdir(parents=True, exist_ok=True)
            continue
        target = destination / path.relative_to(task.starter_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return destination


def snapshot(root: Path) -> Snapshot:
    if not root.is_dir():
        raise WorkspaceError(f"workspace directory does not exist: {root}")
    files: Dict[str, bytes] = {}
    total = 0
    ignored = sorted({p.name for p in root.iterdir() if p.is_dir() and p.name in IGNORED_DIRS})
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if path.is_symlink() and not any(part in IGNORED_DIRS for part in rel_parts[:-1]):
            # Symlinks (to files or directories) could point outside the workspace.
            raise WorkspaceError(f"symbolic links are not allowed in submissions: {path.relative_to(root)}")
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        if path.name == ".gitkeep":
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise WorkspaceError(f"file too large ({size} bytes): {rel}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise WorkspaceError("workspace exceeds the total size limit")
        files[rel] = path.read_bytes()
        if len(files) > MAX_FILES:
            raise WorkspaceError("workspace contains too many files")
    return Snapshot(files=files, ignored_dirs=ignored)


def _matches(rel: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in patterns)


def _text(data: bytes) -> Optional[List[str]]:
    try:
        return data.decode("utf-8").replace("\r\n", "\n").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def diff_snapshots(baseline: Snapshot, submission: Snapshot, task: Task) -> Dict[str, object]:
    scope = task.meta.get("scope", {})
    allowed = list(scope.get("allowed_paths", []))
    protected = list(scope.get("protected_paths", []))
    changed = []
    patch_chunks: List[str] = []
    total_added = total_removed = 0
    for rel in sorted(set(baseline.files) | set(submission.files)):
        before = baseline.files.get(rel)
        after = submission.files.get(rel)
        if before is not None and after is not None and before.replace(b"\r\n", b"\n") == after.replace(b"\r\n", b"\n"):
            continue
        change = "added" if before is None else "deleted" if after is None else "modified"
        old_lines = _text(before) if before is not None else []
        new_lines = _text(after) if after is not None else []
        added = removed = 0
        binary = old_lines is None or new_lines is None
        if not binary:
            diff = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{rel}" if before is not None else "/dev/null",
                    tofile=f"b/{rel}" if after is not None else "/dev/null",
                )
            )
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed += 1
            text = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in diff)
            patch_chunks.append(text)
        else:
            patch_chunks.append(f"Binary files a/{rel} and b/{rel} differ\n")
        total_added += added
        total_removed += removed
        in_scope = _matches(rel, allowed) and not _matches(rel, protected)
        changed.append(
            {
                "path": rel,
                "change": change,
                "lines_added": added,
                "lines_removed": removed,
                "binary": binary,
                "in_scope": in_scope,
                "protected": _matches(rel, protected),
                "harness_sensitive": Path(rel).name in HARNESS_SENSITIVE_FILES and "/" not in rel,
            }
        )
    return {
        "changed_files": changed,
        "files_changed": len(changed),
        "lines_added": total_added,
        "lines_removed": total_removed,
        "out_of_scope_files": [c["path"] for c in changed if not c["in_scope"]],
        "protected_files_modified": [c["path"] for c in changed if c["protected"]],
        "harness_sensitive_files": [c["path"] for c in changed if c["harness_sensitive"]],
        "ignored_tool_directories": submission.ignored_dirs,
        "patch": "".join(patch_chunks),
    }


# "paths" ini options are resolved relative to the ini file (which lives in _acb/).
PYTEST_INI = """[pytest]
pythonpath = .. support
addopts =
python_files = test_*.py *_test.py
junit_family = xunit2
console_output_style = classic
"""


def prepare_eval_dir(task: Task, submission: Snapshot, baseline: Snapshot, eval_dir: Path) -> Dict[str, object]:
    """Materialise the submission plus the hidden grading assets in a fresh directory.

    Protected files are restored from the starter and harness-sensitive files at the workspace
    root (e.g. a ``conftest.py`` or ``sitecustomize.py`` that could alter test outcomes) are removed.
    Both actions are reported so that they can be audited.
    """
    eval_dir.mkdir(parents=True, exist_ok=False)
    protected = list(task.meta.get("scope", {}).get("protected_paths", []))
    restored: List[str] = []
    removed: List[str] = []
    for rel, data in submission.files.items():
        if rel.split("/")[0] == "_acb":
            removed.append(rel)
            continue
        if "/" not in rel and rel in HARNESS_SENSITIVE_FILES:
            removed.append(rel)
            continue
        if _matches(rel, protected):
            continue
        target = eval_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for rel, data in baseline.files.items():
        if _matches(rel, protected):
            target = eval_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if submission.files.get(rel) != data:
                restored.append(rel)
    acb = eval_dir / "_acb"
    shutil.copytree(task.grading_dir, acb / "grading")
    (acb / "support").mkdir(parents=True)
    shutil.copyfile(SUPPORT_DIR / "acb_coverage.py", acb / "support" / "acb_coverage.py")
    (acb / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    out = acb / "out"
    out.mkdir()
    for path in (eval_dir, acb, out):
        path.chmod(0o777)  # allow the unprivileged container user to write reports and tmp files
    return {"restored_protected_files": sorted(restored), "removed_harness_files": sorted(removed)}
