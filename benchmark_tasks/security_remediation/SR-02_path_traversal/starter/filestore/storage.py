"""Store and serve user files beneath a base directory."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

PathLike = Union[str, "os.PathLike[str]"]


def read_user_file(base_dir: PathLike, user_path: str) -> bytes:
    target = os.path.join(base_dir, user_path)
    with open(target, "rb") as handle:
        return handle.read()


def save_upload(base_dir: PathLike, filename: str, data: bytes) -> Path:
    target = Path(os.path.join(base_dir, filename))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target.resolve()
