"""Well-known locations and file-walking rules shared by the evaluator modules."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(os.environ.get("ACB_REPO_ROOT", PACKAGE_DIR.parent)).resolve()
TASKS_ROOT = Path(os.environ.get("ACB_TASKS_ROOT", REPO_ROOT / "benchmark_tasks")).resolve()
VALIDATION_DIR = TASKS_ROOT / "_validation"
CONFIG_DIR = PACKAGE_DIR / "config"
SUPPORT_DIR = PACKAGE_DIR / "support"

CATEGORIES = (
    "bug_fixing",
    "feature_implementation",
    "security_remediation",
    "refactoring",
    "test_writing",
    "repository_reasoning",
)

# Directories that never belong to a submission: VCS data, caches, virtual environments and the
# metadata folders that coding assistants or editors create in a workspace.
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".idea",
        ".vscode",
        ".cursor",
        ".claude",
        ".codex",
        ".copilot",
        ".github",
        ".DS_Store",
    }
)
IGNORED_SUFFIXES = (".pyc", ".pyo")
IGNORED_FILES = frozenset({".DS_Store", "Thumbs.db"})

# Files at the workspace root that could change how the evaluator's Python or pytest behaves.
HARNESS_SENSITIVE_FILES = frozenset(
    {
        "conftest.py",
        "sitecustomize.py",
        "usercustomize.py",
        "pytest.ini",
        "pyproject.toml",
        "setup.cfg",
        "tox.ini",
    }
)

# Limits that protect the evaluator from oversized or malicious workspaces.
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 20_000_000
MAX_FILES = 2_000
MAX_CAPTURE_BYTES = 256_000
