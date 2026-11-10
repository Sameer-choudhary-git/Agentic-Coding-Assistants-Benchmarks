"""Subprocess execution with timeouts, bounded output capture and a scrubbed environment."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from evaluator.paths import MAX_CAPTURE_BYTES

# Environment variables that are passed through to evaluated code. Everything else (API keys,
# tokens, cloud credentials, PYTHONPATH, PYTEST_ADDOPTS, ...) is dropped.
_PASSTHROUGH = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "LANG", "TZ")


@dataclass
class ProcResult:
    command: List[str]
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "duration_s": round(self.duration_s, 3),
            "timed_out": self.timed_out,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "error": self.error,
        }


def scrubbed_env(extra: Optional[Dict[str, str]] = None, home: Optional[Path] = None) -> Dict[str, str]:
    env = {key: os.environ[key] for key in _PASSTHROUGH if key in os.environ}
    temp = str(home) if home else tempfile.gettempdir()
    env.update(
        {
            "HOME": temp,
            "USERPROFILE": temp,
            "TMPDIR": temp,
            "TEMP": temp,
            "TMP": temp,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "NO_COLOR": "1",
        }
    )
    if extra:
        env.update(extra)
    return env


def _read_bounded(path: Path) -> tuple:
    size = path.stat().st_size
    with open(path, "rb") as handle:
        data = handle.read(MAX_CAPTURE_BYTES)
    text = data.decode("utf-8", errors="replace")
    truncated = size > MAX_CAPTURE_BYTES
    if truncated:
        text += f"\n[... output truncated: {size - MAX_CAPTURE_BYTES} more bytes ...]\n"
    return text, truncated


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run(
    command: Sequence[str],
    cwd: Path,
    timeout_s: float,
    env: Optional[Dict[str, str]] = None,
) -> ProcResult:
    """Run ``command`` (never through a shell) and capture bounded stdout/stderr."""
    command = [str(part) for part in command]
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="acb-proc-") as tmp:
        out_path = Path(tmp) / "stdout"
        err_path = Path(tmp) / "stderr"
        with open(out_path, "wb") as out, open(err_path, "wb") as err:
            kwargs = {}
            if os.name != "nt":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:
                proc = subprocess.Popen(command, cwd=str(cwd), env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL, **kwargs)
            except OSError as exc:
                return ProcResult(command, None, "", "", time.monotonic() - started, False, False, False, str(exc))
            timed_out = False
            try:
                exit_code = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_tree(proc)
                try:
                    exit_code = proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    exit_code = None
        stdout, out_trunc = _read_bounded(out_path)
        stderr, err_trunc = _read_bounded(err_path)
    return ProcResult(command, exit_code, stdout, stderr, time.monotonic() - started, timed_out, out_trunc, err_trunc)


def find_tool(name: str, env_var: str) -> Optional[List[str]]:
    """Locate a command-line tool: explicit env override, then PATH, then ``python -m <name>``."""
    override = os.environ.get(env_var)
    if override:
        resolved = shutil.which(override)
        return [resolved] if resolved else None
    found = shutil.which(name)
    if found:
        return [found]
    if name == "ruff":
        try:
            import ruff  # noqa: F401

            return [sys.executable, "-m", "ruff"]
        except ImportError:
            return None
    return None


def tool_version(command: Optional[List[str]], flag: str = "--version") -> Optional[str]:
    if not command:
        return None
    result = run([*command, flag], cwd=Path.cwd(), timeout_s=60, env=None)
    if result.exit_code != 0:
        return None
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0].strip() if text else None
