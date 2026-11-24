"""Execution backends that run pytest against an evaluation directory.

Two modes are supported:

* ``docker`` (recommended for the official experiment): pytest runs inside a disposable container
  with no network, a read-only root filesystem, dropped capabilities, a non-root user, memory/CPU/PID
  limits and a wall-clock timeout.
* ``local``: pytest runs as a child process on the host with a scrubbed environment and a timeout.
  It provides **no** filesystem or network isolation and must be selected explicitly.
"""

from __future__ import annotations

import os
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from evaluator.procs import ProcResult, run, scrubbed_env

DEFAULT_IMAGE = os.environ.get("ACB_DOCKER_IMAGE", "acb-evaluator:1.0")
MODES = ("docker", "local")



# ``-p acb_coverage`` is imported before pytest applies the ini ``pythonpath`` option, and ``python -I`` ignores
# PYTHONPATH and the current directory, so the support directory is put on sys.path before pytest starts.
# Paths are relative to the evaluation directory (the working directory locally and /work in Docker).
PYTEST_BOOTSTRAP = "import sys; sys.path.insert(0, '_acb/support'); import pytest; sys.exit(pytest.main(sys.argv[1:]))"

class ExecutionUnavailable(Exception):
    """The requested execution backend cannot be used on this machine."""


@dataclass
class PytestOutcome:
    proc: ProcResult
    tests: List[Dict[str, object]]
    passed: int
    failed: int
    errors: int
    skipped: int
    collection_error: bool
    junit_found: bool

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped


def parse_junit(path: Path) -> Optional[List[Dict[str, object]]]:
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    tests = []
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        outcome = "passed"
        message = None
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (node.get("message") or (node.text or ""))[:2000]
                break
        tests.append(
            {
                "id": f"{classname.rsplit('.', 1)[-1]}::{name}" if classname else name,
                "classname": classname,
                "name": name,
                "outcome": outcome,
                "duration_s": float(case.get("time") or 0.0),
                "message": message,
            }
        )
    return tests


class Executor:
    mode: str = ""

    def run_pytest(
        self,
        eval_dir: Path,
        targets: List[str],
        junit_name: str,
        timeout_s: float,
        coverage_targets: Optional[List[str]] = None,
        coverage_out: Optional[str] = None,
        allow_conftest: bool = False,
        fail_fast: bool = False,
    ) -> PytestOutcome:
        junit_rel = f"_acb/out/{junit_name}"
        args = [
            "-c",
            PYTEST_BOOTSTRAP,
            *targets,
            "-c",
            "_acb/pytest.ini",
            "--rootdir",
            ".",
            "-p",
            "no:cacheprovider",
            "--import-mode=importlib",
            "-q",
            "-rN",
            f"--junitxml={junit_rel}",
        ]
        if not allow_conftest:
            args.append("--noconftest")
        if fail_fast:
            args.append("-x")
        extra_env: Dict[str, str] = {}
        if coverage_targets:
            args += ["-p", "acb_coverage"]
            extra_env["ACB_COVERAGE_TARGETS"] = os.pathsep.join(coverage_targets)
            extra_env["ACB_COVERAGE_OUT"] = coverage_out or "_acb/out/coverage.json"
        junit_path = eval_dir / junit_rel
        if junit_path.exists():
            junit_path.unlink()
        proc = self._execute(eval_dir, args, extra_env, timeout_s)
        tests = parse_junit(junit_path)
        junit_found = tests is not None
        tests = tests or []
        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for test in tests:
            counts[str(test["outcome"])] += 1
        collection_error = proc.exit_code in (2, 3, 4) or (proc.exit_code not in (0, 1, 5) and not proc.timed_out)
        return PytestOutcome(
            proc=proc,
            tests=tests,
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["error"],
            skipped=counts["skipped"],
            collection_error=collection_error,
            junit_found=junit_found,
        )

    def _execute(self, eval_dir: Path, args: List[str], extra_env: Dict[str, str], timeout_s: float) -> ProcResult:
        raise NotImplementedError

    def describe(self) -> Dict[str, object]:
        raise NotImplementedError


class LocalExecutor(Executor):
    mode = "local"

    def __init__(self, python: Optional[str] = None) -> None:
        self.python = python or os.environ.get("ACB_EVAL_PYTHON") or sys.executable

    def _execute(self, eval_dir: Path, args: List[str], extra_env: Dict[str, str], timeout_s: float) -> ProcResult:
        home = eval_dir / "_acb" / "home"
        home.mkdir(exist_ok=True)
        env = scrubbed_env(extra_env, home=home)
        return run([self.python, "-I", *args], cwd=eval_dir, timeout_s=timeout_s, env=env)

    def describe(self) -> Dict[str, object]:
        version = run(
            [self.python, "-I", "-c", "import sys,pytest;print(sys.version.split()[0], pytest.__version__)"],
            cwd=Path.cwd(),
            timeout_s=60,
            env=scrubbed_env(),
        )
        parts = version.stdout.split()
        return {
            "mode": self.mode,
            "isolation": "none (host subprocess with scrubbed environment and timeout)",
            "python": parts[0] if len(parts) == 2 else None,
            "pytest": parts[1] if len(parts) == 2 else None,
            "network_disabled": False,
        }


class DockerExecutor(Executor):
    mode = "docker"

    def __init__(self, image: str = DEFAULT_IMAGE) -> None:
        self.image = image
        self.docker = shutil.which("docker")
        if not self.docker:
            raise ExecutionUnavailable("docker executable not found on PATH")
        info = run([self.docker, "info", "--format", "{{.ServerVersion}}"], cwd=Path.cwd(), timeout_s=30)
        if info.exit_code != 0:
            raise ExecutionUnavailable("Docker daemon is not reachable: " + (info.stderr.strip() or "unknown error"))
        self.server_version = info.stdout.strip()
        inspect = run([self.docker, "image", "inspect", self.image], cwd=Path.cwd(), timeout_s=30)
        if inspect.exit_code != 0:
            raise ExecutionUnavailable(
                f"Docker image {self.image} is missing; build it with: docker build -t {self.image} -f docker/evaluator.Dockerfile ."
            )

    def _execute(self, eval_dir: Path, args: List[str], extra_env: Dict[str, str], timeout_s: float) -> ProcResult:
        name = f"acb-eval-{uuid.uuid4().hex[:12]}"
        env_flags: List[str] = []
        for key, value in {
            **extra_env,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "HOME": "/tmp",
        }.items():
            env_flags += ["-e", f"{key}={value}"]
        command = [
            self.docker,
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--memory",
            os.environ.get("ACB_DOCKER_MEMORY", "1g"),
            "--memory-swap",
            os.environ.get("ACB_DOCKER_MEMORY", "1g"),
            "--cpus",
            os.environ.get("ACB_DOCKER_CPUS", "1"),
            "--pids-limit",
            "256",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=128m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10001:10001",
            *env_flags,
            "-v",
            f"{eval_dir.resolve()}:/work:rw",
            "-w",
            "/work",
            self.image,
            "python",
            "-I",
            *args,
        ]
        result = run(command, cwd=eval_dir, timeout_s=timeout_s + 30)
        if result.timed_out:
            run([self.docker, "rm", "-f", name], cwd=eval_dir, timeout_s=30)
        return result

    def describe(self) -> Dict[str, object]:
        probe = run(
            [
                self.docker,
                "run",
                "--rm",
                "--network",
                "none",
                self.image,
                "python",
                "-c",
                "import sys,pytest;print(sys.version.split()[0], pytest.__version__)",
            ],
            cwd=Path.cwd(),
            timeout_s=120,
        )
        parts = probe.stdout.split()
        return {
            "mode": self.mode,
            "isolation": "docker: no network, read-only rootfs, non-root, cap-drop ALL, memory/cpu/pid limits",
            "image": self.image,
            "docker_server": self.server_version,
            "python": parts[0] if len(parts) == 2 else None,
            "pytest": parts[1] if len(parts) == 2 else None,
            "network_disabled": True,
        }


def make_executor(mode: str) -> Executor:
    if mode == "local":
        return LocalExecutor()
    if mode == "docker":
        return DockerExecutor()
    raise ExecutionUnavailable(f"unknown execution mode: {mode!r} (expected one of {MODES})")
