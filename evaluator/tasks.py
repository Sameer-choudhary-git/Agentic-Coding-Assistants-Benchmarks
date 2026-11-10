"""Task discovery, metadata loading and content hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from evaluator.paths import CATEGORIES, IGNORED_DIRS, IGNORED_FILES, IGNORED_SUFFIXES, TASKS_ROOT, VALIDATION_DIR

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "difficulty",
    "difficulty_rationale",
    "version",
    "test_version",
    "kind",
    "summary",
    "required_behavior",
    "acceptance_criteria",
    "acceptance_tests",
    "scope",
    "time_limit_minutes",
    "test_timeout_seconds",
)
DIFFICULTIES = ("easy", "medium", "hard")
KINDS = ("standard", "test_writing")


class TaskError(Exception):
    """Raised when a task cannot be found or is malformed."""


def iter_files(root: Path) -> Iterable[Path]:
    """Yield files under ``root`` in a stable order, skipping caches and tool metadata."""
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        rel_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in rel_parts[:-1]):
            continue
        if path.is_dir():
            continue
        if path.name in IGNORED_FILES or path.suffix in IGNORED_SUFFIXES or path.name in IGNORED_DIRS:
            continue
        yield path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_tree(root: Path) -> str:
    """Hash every file's relative path and content. Line endings are normalised so that
    checkouts on Windows (CRLF) and Unix (LF) produce the same hash."""
    digest = hashlib.sha256()
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(rel.encode("utf-8") + b"\0" + sha256_bytes(data).encode("ascii") + b"\n")
    return digest.hexdigest()


def hash_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


@dataclass
class Task:
    root: Path
    meta: Dict[str, Any]

    @property
    def id(self) -> str:
        return str(self.meta["id"])

    @property
    def kind(self) -> str:
        return str(self.meta.get("kind", "standard"))

    @property
    def starter_dir(self) -> Path:
        return self.root / "starter"

    @property
    def grading_dir(self) -> Path:
        return self.root / "grading"

    @property
    def reference_dir(self) -> Path:
        return self.root / "reference"

    @property
    def prompt_path(self) -> Path:
        return self.root / "prompt.md"

    def prompt(self) -> str:
        return self.prompt_path.read_text(encoding="utf-8")

    def hashes(self) -> Dict[str, str]:
        starter = hash_tree(self.starter_dir)
        tests = hash_tree(self.grading_dir)
        prompt = hash_file(self.prompt_path)
        meta = hash_file(self.root / "task.json")
        combined = sha256_bytes(f"{meta}|{prompt}|{starter}|{tests}".encode("ascii"))
        return {
            "task_hash": combined,
            "prompt_hash": prompt,
            "starter_hash": starter,
            "test_hash": tests,
            "metadata_hash": meta,
            "reference_hash": hash_tree(self.reference_dir),
        }

    def starter_files(self) -> List[Dict[str, Any]]:
        files = []
        for path in iter_files(self.starter_dir):
            rel = path.relative_to(self.starter_dir).as_posix()
            if path.name == ".gitkeep":
                continue
            files.append({"path": rel, "size": path.stat().st_size})
        return files

    def validation_record(self) -> Optional[Dict[str, Any]]:
        path = VALIDATION_DIR / f"{self.id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def validation_status(self) -> Dict[str, Any]:
        record = self.validation_record()
        if record is None:
            return {"status": "not_validated", "validated_at": None, "expected_acceptance_total": None}
        current = self.hashes()["task_hash"]
        if record.get("task_hash") != current:
            status = "stale"
        else:
            status = "validated" if record.get("passed") else "failed"
        return {
            "status": status,
            "validated_at": record.get("validated_at"),
            "expected_acceptance_total": record.get("expected_acceptance_total"),
            "evaluator_version": record.get("evaluator_version"),
            "execution_mode": record.get("execution_mode"),
        }

    def public_summary(self) -> Dict[str, Any]:
        """Metadata that may be shown to researchers. Hidden test code and reference solutions are
        never included; acceptance tests are described only by id and description."""
        keys = [
            "id",
            "title",
            "category",
            "difficulty",
            "difficulty_rationale",
            "version",
            "test_version",
            "kind",
            "summary",
            "required_behavior",
            "acceptance_criteria",
            "acceptance_tests",
            "scope",
            "time_limit_minutes",
            "test_timeout_seconds",
            "test_writing",
        ]
        summary = {k: self.meta[k] for k in keys if k in self.meta}
        summary["directory"] = self.root.relative_to(TASKS_ROOT).as_posix()
        summary["starter_location"] = f"benchmark_tasks/{summary['directory']}/starter"
        summary["starter_files"] = self.starter_files()
        summary["prompt"] = self.prompt()
        summary.update(self.hashes())
        summary.pop("reference_hash", None)
        summary["validation"] = self.validation_status()
        return summary


def check_metadata(meta: Dict[str, Any], directory: Path) -> List[str]:
    problems = [f"missing field: {name}" for name in REQUIRED_FIELDS if name not in meta]
    if meta.get("category") not in CATEGORIES:
        problems.append(f"unknown category: {meta.get('category')!r}")
    elif directory.parent.name != meta["category"]:
        problems.append("task directory is not inside its category folder")
    if meta.get("difficulty") not in DIFFICULTIES:
        problems.append(f"unknown difficulty: {meta.get('difficulty')!r}")
    if meta.get("kind") not in KINDS:
        problems.append(f"unknown kind: {meta.get('kind')!r}")
    if meta.get("kind") == "test_writing":
        tw = meta.get("test_writing") or {}
        for key in ("target_module", "test_paths", "min_tests", "min_line_coverage", "min_mutation_score"):
            if key not in tw:
                problems.append(f"test_writing.{key} missing")
    scope = meta.get("scope") or {}
    if not isinstance(scope.get("allowed_paths"), list):
        problems.append("scope.allowed_paths must be a list")
    if not str(meta.get("id", "")).strip():
        problems.append("id is empty")
    return problems


def load_task_dir(directory: Path) -> Task:
    meta_path = directory / "task.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TaskError(f"cannot read {meta_path}: {exc}") from exc
    problems = check_metadata(meta, directory)
    if problems:
        raise TaskError(f"{meta_path}: " + "; ".join(problems))
    for required in ("starter", "grading", "reference"):
        if not (directory / required).is_dir():
            raise TaskError(f"{directory}: missing {required}/ directory")
    if not (directory / "prompt.md").is_file():
        raise TaskError(f"{directory}: missing prompt.md")
    return Task(root=directory, meta=meta)


def discover_tasks() -> List[Task]:
    tasks: List[Task] = []
    seen = set()
    for category in CATEGORIES:
        category_dir = TASKS_ROOT / category
        if not category_dir.is_dir():
            continue
        for directory in sorted(p for p in category_dir.iterdir() if (p / "task.json").is_file()):
            task = load_task_dir(directory)
            if task.id in seen:
                raise TaskError(f"duplicate task id {task.id}")
            seen.add(task.id)
            tasks.append(task)
    return tasks


def get_task(task_id: str) -> Task:
    for task in discover_tasks():
        if task.id == task_id:
            return task
    raise TaskError(f"unknown task id: {task_id}")
