"""Session token and settings (de)serialisation."""

from __future__ import annotations

import base64
import pickle
from typing import Any, Dict


def encode_session(data: Dict[str, Any], secret: bytes) -> str:
    """Serialise ``data`` into a token that can be stored in a cookie."""
    return base64.urlsafe_b64encode(pickle.dumps(data)).decode("ascii")


def decode_session(token: str, secret: bytes) -> Dict[str, Any]:
    """Return the session dictionary stored in ``token``."""
    return pickle.loads(base64.urlsafe_b64decode(token.encode("ascii")))


def parse_settings(text: str) -> Dict[str, Any]:
    """Parse ``key = value`` lines. Blank lines and ``#`` comments are ignored."""
    settings: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        settings[key.strip()] = eval(value.strip())
    return settings
