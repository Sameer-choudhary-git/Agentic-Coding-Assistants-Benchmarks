"""Session token and settings (de)serialisation."""

from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import json
from typing import Any, Dict


class InvalidSession(ValueError):
    """Raised when a session token is malformed or fails verification."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))


def _sign(payload: str, secret: bytes) -> str:
    return _b64(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())


def encode_session(data: Dict[str, Any], secret: bytes) -> str:
    """Serialise ``data`` into a signed, URL-safe token."""
    try:
        raw = json.dumps(data, separators=(",", ":"), sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"session data is not JSON-serialisable: {exc}") from exc
    payload = _b64(raw.encode("utf-8"))
    return f"{payload}.{_sign(payload, secret)}"


def decode_session(token: str, secret: bytes) -> Dict[str, Any]:
    """Verify ``token`` and return the session dictionary."""
    if not isinstance(token, str) or token.count(".") != 1:
        raise InvalidSession("malformed token")
    payload, signature = token.split(".")
    try:
        expected = _sign(payload, secret)
    except (UnicodeEncodeError, ValueError) as exc:
        raise InvalidSession("malformed token") from exc
    if not hmac.compare_digest(expected, signature):
        raise InvalidSession("bad signature")
    try:
        data = json.loads(_unb64(payload).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise InvalidSession("malformed payload") from exc
    if not isinstance(data, dict):
        raise InvalidSession("payload is not an object")
    return data


def parse_settings(text: str) -> Dict[str, Any]:
    """Parse ``key = value`` lines. Blank lines and ``#`` comments are ignored."""
    settings: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        try:
            settings[key.strip()] = ast.literal_eval(value.strip())
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError) as exc:
            raise ValueError(f"invalid value for {key.strip()!r}") from exc
    return settings
