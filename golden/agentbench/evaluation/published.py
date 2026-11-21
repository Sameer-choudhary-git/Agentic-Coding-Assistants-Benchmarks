"""Import published agent runs from the SWE-bench experiments repository."""
from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import requests
import yaml

log = logging.getLogger(__name__)


def _get(url: str, timeout: int = 120) -> requests.Response | None:
    for _ in range(3):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code in (200, 404):
                return r
        except requests.RequestException:
            pass
    return None


class PublishedRun:
    def __init__(self, spec: dict, reg: dict, cache_dir: str):
        self.spec = spec
        self.id = spec["id"]
        self.raw = reg["experiments_raw"].rstrip("/") + "/" + spec["dir"]
        self.s3 = reg["submissions_s3"].rstrip("/")
        self.dir = os.path.join(cache_dir, "agents", self.id)
        os.makedirs(self.dir, exist_ok=True)

    # ---------------------------------------------------------------- outcomes
    def resolved(self) -> dict[str, bool] | None:
        path = os.path.join(self.dir, "resolved.json")
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8"))
        out: dict[str, bool] | None = None
        if self.spec["kind"] == "bash_only":
            r = _get(self.raw + "/per_instance_details.json")
            if r is not None and r.status_code == 200:
                out = {k: bool(v.get("resolved")) for k, v in r.json().items()}
            # some submissions publish an unpopulated per_instance_details.json (all false);
            # fall back to the per-instance harness reports, which are authoritative
            if not out or not any(out.values()):
                ids = list(out) if out else []
                if ids:
                    def one(iid: str) -> tuple[str, bool]:
                        rr = _get(f"{self.s3}/bash-only/{self.spec['dir']}/logs/{iid}/report.json", timeout=60)
                        try:
                            return iid, bool(rr is not None and rr.status_code == 200 and rr.json().get("resolved"))
                        except ValueError:
                            return iid, False
                    with ThreadPoolExecutor(16) as ex:
                        out = dict(ex.map(one, ids))
                    log.info("%s: rebuilt outcomes from %d per-instance reports", self.id, len(ids))
        else:
            r = _get(self.raw + "/results/results.json")
            if r is not None and r.status_code == 200:
                res = set(r.json().get("resolved", []))
                out = {"__resolved_list__": True, **{i: True for i in res}}
        if out is not None:
            json.dump(out, open(path, "w", encoding="utf-8"))
        return out

    def is_resolved(self, resolved: dict, iid: str) -> bool:
        return bool(resolved.get(iid, False))

    # ---------------------------------------------------------------- patches
    def patches(self, instance_ids: list[str]) -> dict[str, str]:
        path = os.path.join(self.dir, "patches.json")
        cache: dict[str, str] = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        missing = [i for i in instance_ids if i not in cache]
        if missing and self.spec["kind"] == "s3_preds":
            r = _get(f"{self.s3}/verified/{self.spec['dir']}/all_preds.jsonl", timeout=300)
            if r is not None and r.status_code == 200:
                for line in r.text.splitlines():
                    if line.strip():
                        d = json.loads(line)
                        cache[d["instance_id"]] = d.get("model_patch") or ""
            for i in missing:
                cache.setdefault(i, "")
        elif missing:
            def one(iid: str) -> tuple[str, str]:
                rr = _get(f"{self.s3}/bash-only/{self.spec['dir']}/logs/{iid}/patch.diff", timeout=60)
                return iid, (rr.text if rr is not None and rr.status_code == 200 else "")
            with ThreadPoolExecutor(12) as ex:
                for iid, p in ex.map(one, missing):
                    cache[iid] = p
        json.dump(cache, open(path, "w", encoding="utf-8"))
        return {i: cache.get(i, "") for i in instance_ids}


def load_registry(path: str = "configs/agents.yaml") -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
