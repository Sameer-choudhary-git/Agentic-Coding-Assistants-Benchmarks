"""Store and serve user files beneath a base directory."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Union

PathLike = Union[str, "os.PathLike[str]"]


class UnsafePathError(ValueError):
    """Raised when a user-supplied path would escape the storage directory."""


def _safe_target(base_dir: PathLike, user_path: str) -> Path:
    if not isinstance(user_path, str) or not user_path.strip():
        raise UnsafePathError("empty path")
    if "\x00" in user_path:
        raise UnsafePathError("NUL byte in path")
    if PurePosixPath(user_path).is_absolute() or PureWindowsPath(user_path).is_absolute():
        raise UnsafePathError("absolute paths are not allowed")
    if PureWindowsPath(user_path).drive:
        raise UnsafePathError("drive-qualified paths are not allowed")
    base = Path(base_dir).resolve()
    target = (base / user_path).resolve()
    if target != base and base not in target.parents:
        raise UnsafePathError("path escapes the storage directory")
    if target == base:
        raise UnsafePathError("path refers to the storage directory itself")
    return target


def read_user_file(base_dir: PathLike, user_path: str) -> bytes:
    target = _safe_target(base_dir, user_path)
    with open(target, "rb") as handle:
        return handle.read()


def save_upload(base_dir: PathLike, filename: str, data: bytes) -> Path:
    target = _safe_target(base_dir, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target
