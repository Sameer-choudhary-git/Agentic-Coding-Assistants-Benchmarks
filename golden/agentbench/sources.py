"""Source loaders: download upstream benchmarks and normalise them to GoldenTask."""
from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
from typing import Any, Callable, Iterator

import pandas as pd
import requests

from .diffutil import dominant_language, patch_stats
from .schema import GoldenTask
from .taxonomy import classify

log = logging.getLogger(__name__)
HF_PARQUET = "https://huggingface.co/api/datasets/{hf}/parquet/{split}"


def download(name: str, spec: dict, raw_dir: str, force: bool = False) -> str:
    os.makedirs(raw_dir, exist_ok=True)
    path = os.path.join(raw_dir, f"{name}.parquet")
    if os.path.exists(path) and not force:
        return path
    url = HF_PARQUET.format(**spec)
    log.info("downloading %s <- %s", name, url)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path + ".part", "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    os.replace(path + ".part", path)
    return path


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    if hasattr(v, "tolist"):
        return [str(x) for x in v.tolist()]
    s = str(v).strip()
    if not s:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            out = parser(s)
            if isinstance(out, (list, tuple)):
                return [str(x) for x in out]
        except Exception:  # noqa: BLE001
            pass
    return [s]


def _str(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)


VERIFIED_DIFFICULTY = {"<15 min fix": "easy", "15 min - 1 hour": "medium", "1-4 hours": "hard", ">4 hours": "hard"}
LANG_NORMALISE = {"js": "javascript", "ts": "typescript", "c++": "cpp", "golang": "go"}


def _lang(label: str, patch: str) -> str:
    label = (label or "").strip().lower()
    label = LANG_NORMALISE.get(label, label)
    return label or dominant_language(patch)


def _swe_task(source: str, row: Any, *, human_validated: bool, labels: dict | None = None,
              difficulty: str | None = None, difficulty_source: str = "heuristic",
              language: str = "", f2p_key: str = "FAIL_TO_PASS", p2p_key: str = "PASS_TO_PASS",
              environment: dict | None = None, metadata: dict | None = None) -> GoldenTask:
    patch = _str(row.get("patch"))
    problem = _str(row.get("problem_statement"))
    cls = classify(source=source, problem=problem, patch=patch, labels=labels)
    iid = _str(row.get("instance_id"))
    return GoldenTask(
        task_id=f"{source}::{iid}",
        source=source,
        source_instance_id=iid,
        domain=cls.domain,
        subdomain=cls.subdomain,
        eval_type="fail_to_pass",
        language=_lang(language, patch),
        problem_statement=problem,
        repo=_str(row.get("repo")),
        base_commit=_str(row.get("base_commit")),
        hints=_str(row.get("hints_text")),
        gold_patch=patch,
        test_patch=_str(row.get("test_patch")),
        fail_to_pass=_as_list(row.get(f2p_key)),
        pass_to_pass=_as_list(row.get(p2p_key)),
        difficulty=difficulty or "medium",
        difficulty_source=difficulty_source if difficulty else "pending",
        created_at=_str(row.get("created_at"))[:19],
        human_validated=human_validated,
        domain_confidence=cls.confidence,
        domain_evidence=cls.evidence,
        patch_stats=patch_stats(patch),
        environment=environment or {},
        metadata=metadata or {},
    )


# ---------------------------------------------------------------- loaders
def load_swebench_verified(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        yield _swe_task("swebench_verified", r, human_validated=hv,
                        difficulty=VERIFIED_DIFFICULTY.get(_str(r.get("difficulty"))), difficulty_source="source_label",
                        language="python",
                        environment={"harness": "swebench", "dataset": "princeton-nlp/SWE-bench_Verified",
                                     "environment_setup_commit": _str(r.get("environment_setup_commit")),
                                     "version": _str(r.get("version"))},
                        metadata={"time_estimate": _str(r.get("difficulty"))})


def load_swebench_plusplus(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        yield _swe_task("swebench_plusplus", r, human_validated=hv,
                        labels={"task_type": _str(r.get("task_type")), "repo_type": _str(r.get("repo_type"))},
                        difficulty=_str(r.get("difficulty")) or None, difficulty_source="source_label",
                        language=_str(r.get("language")),
                        environment={"harness": "swebench_plusplus", "config": _str(r.get("environment_config"))},
                        metadata={"task_type": _str(r.get("task_type")), "repo_type": _str(r.get("repo_type"))})


def load_swebench_plus(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        yield _swe_task("swebench_plus", r, human_validated=hv, language="python",
                        environment={"harness": "swebench", "version": _str(r.get("version")),
                                     "environment_setup_commit": _str(r.get("environment_setup_commit"))})


def load_swebench_pro(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        spec = _as_list(r.get("issue_specificity"))
        cats = _as_list(r.get("issue_categories"))
        problem = _str(r.get("problem_statement"))
        req = _str(r.get("requirements"))
        iface = _str(r.get("interface"))
        if req:
            problem += "\n\n## Requirements\n" + req
        if iface and iface.lower() not in ("none", "no new interfaces are introduced"):
            problem += "\n\n## Interface\n" + iface
        r = dict(r)
        r["problem_statement"] = problem
        yield _swe_task("swebench_pro", r, human_validated=hv,
                        labels={"issue_specificity": spec, "issue_categories": cats},
                        difficulty="hard" if bool(r.get("hard")) else None, difficulty_source="source_label",
                        language=_str(r.get("repo_language")), f2p_key="fail_to_pass", p2p_key="pass_to_pass",
                        environment={"harness": "swebench_pro", "docker_image": _str(r.get("docker_image")),
                                     "before_repo_set_cmd": _str(r.get("before_repo_set_cmd")),
                                     "selected_test_files_to_run": _as_list(r.get("selected_test_files_to_run"))},
                        metadata={"issue_specificity": spec, "issue_categories": cats})


def load_swebench_multimodal(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        assets = r.get("image_assets")
        try:
            assets = json.loads(assets) if isinstance(assets, str) else assets
            imgs = list(assets.get("problem_statement", [])) if isinstance(assets, dict) else []
        except Exception:  # noqa: BLE001
            imgs = []
        yield _swe_task("swebench_multimodal", r, human_validated=hv, language="javascript",
                        environment={"harness": "swebench", "dataset": "SWE-bench/SWE-bench_Multimodal",
                                     "version": _str(r.get("version"))},
                        metadata={"image_assets": [str(x) for x in imgs]})


def load_swebench_multilingual(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        yield _swe_task("swebench_multilingual", r, human_validated=hv,
                        environment={"harness": "swebench", "dataset": "SWE-bench/SWE-bench_Multilingual",
                                     "version": _str(r.get("version"))})


def load_swe_rebench(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        meta = r.get("meta") or {}
        llm = dict(meta.get("llm_score") or {}) if isinstance(meta, dict) else {}
        d = llm.get("difficulty_score")
        diff = {0: "easy", 1: "easy", 2: "medium", 3: "hard"}.get(d) if d is not None else None
        yield _swe_task("swe_rebench", r, human_validated=hv, difficulty=diff, difficulty_source="source_llm_label",
                        environment={"harness": "swe_rebench", "docker_image": _str(r.get("docker_image")),
                                     "install_config": _str(r.get("install_config"))},
                        metadata={"llm_score": {k: int(v) for k, v in llm.items() if v is not None},
                                  "license": _str(r.get("license_name"))})


def load_nyu_ctf(df: pd.DataFrame, hv: bool) -> Iterator[GoldenTask]:
    for _, r in df.iterrows():
        instr = _str(r.get("instruction"))
        cat = (re.search(r"Category:\s*(\w+)", instr) or [None, "misc"])[1]
        loc = _str(r.get("location"))
        m = re.match(r"(\d{4})([qf])", loc)
        event = {"q": "qualifier", "f": "final"}.get(m.group(2), "unknown") if m else "unknown"
        cls = classify(source="nyu_ctf", problem=instr, labels={"ctf_category": cat})
        try:
            cfg = json.loads(_str(r.get("config")))
        except Exception:  # noqa: BLE001
            cfg = {}
        yield GoldenTask(
            task_id=f"nyu_ctf::{loc}", source="nyu_ctf", source_instance_id=loc,
            domain=cls.domain, subdomain=cls.subdomain, eval_type="flag_match",
            language={"pwn": "c/binary", "rev": "binary", "crypto": "python", "web": "web",
                      "forensics": "mixed", "misc": "mixed"}.get(cat, "mixed"),
            problem_statement=instr,
            difficulty="hard" if event == "final" else "medium",
            difficulty_source="ctf_event_tier",
            human_validated=hv, domain_confidence=cls.confidence, domain_evidence=cls.evidence,
            environment={"harness": "harbor", "dataset": "penfever/nyuctf-harbor",
                         "resources": cfg.get("environment", {}), "agent_timeout_sec": cfg.get("agent", {}).get("timeout_sec")},
            metadata={"ctf_category": cat, "event_tier": event, "year": m.group(1) if m else "",
                      "files": _as_list(r.get("files")), "benchmark_lineage": "NYU CTF Bench (used by SWE-agent EnIGMA)"},
        )


LOADERS: dict[str, Callable[[pd.DataFrame, bool], Iterator[GoldenTask]]] = {
    "swebench_verified": load_swebench_verified,
    "swebench_plusplus": load_swebench_plusplus,
    "swebench_plus": load_swebench_plus,
    "swebench_pro": load_swebench_pro,
    "swebench_multimodal": load_swebench_multimodal,
    "swebench_multilingual": load_swebench_multilingual,
    "swe_rebench": load_swe_rebench,
    "nyu_ctf": load_nyu_ctf,
}


def load_all(cfg: dict, force: bool = False) -> tuple[list[GoldenTask], dict]:
    tasks: list[GoldenTask] = []
    manifest = {}
    for name, spec in cfg["sources"].items():
        path = download(name, spec, cfg["paths"]["raw"], force=force)
        df = pd.read_parquet(path)
        before = len(tasks)
        tasks.extend(LOADERS[name](df, bool(spec.get("human_validated"))))
        manifest[name] = {"hf": spec["hf"], "split": spec["split"], "rows": len(df),
                          "sha256": sha256(path), "loaded": len(tasks) - before}
        log.info("%-22s %5d tasks", name, len(tasks) - before)
    return tasks, manifest
