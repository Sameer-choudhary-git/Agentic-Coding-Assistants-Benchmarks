"""Fetch individual files at a commit from GitHub with an on-disk cache."""
from __future__ import annotations

import hashlib
import os
import threading
import time

import requests

RAW = "https://raw.githubusercontent.com/{repo}/{commit}/{path}"
_session = threading.local()


def _sess() -> requests.Session:
    if not hasattr(_session, "s"):
        s = requests.Session()
        s.headers["User-Agent"] = "agentbench-golden/1.0 (research dataset builder)"
        _session.s = s
    return _session.s


class FileFetcher:
    def __init__(self, cache_dir: str, max_bytes: int = 400_000):
        self.dir = os.path.join(cache_dir, "files")
        os.makedirs(self.dir, exist_ok=True)
        self.max_bytes = max_bytes

    def _key(self, repo: str, commit: str, path: str) -> str:
        h = hashlib.sha1(f"{repo}@{commit}:{path}".encode()).hexdigest()
        return os.path.join(self.dir, h[:2], h)

    def get(self, repo: str, commit: str, path: str) -> str | None:
        key = self._key(repo, commit, path)
        if os.path.exists(key):
            with open(key, "rb") as fh:
                data = fh.read()
            return None if data == b"\x00MISSING" else data.decode("utf-8", "replace")
        url = RAW.format(repo=repo, commit=commit, path=path)
        data: bytes | None = None
        for attempt in range(3):
            try:
                r = _sess().get(url, timeout=30)
                if r.status_code == 200:
                    data = r.content
                    break
                if r.status_code == 404:
                    break
                time.sleep(1.5 * (attempt + 1))
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
        else:
            return None  # transient failure: do not cache
        os.makedirs(os.path.dirname(key), exist_ok=True)
        with open(key, "wb") as fh:
            fh.write(data if data is not None and len(data) <= self.max_bytes else b"\x00MISSING")
        if data is None or len(data) > self.max_bytes:
            return None
        return data.decode("utf-8", "replace")
