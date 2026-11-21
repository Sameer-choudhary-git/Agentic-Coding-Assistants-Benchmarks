"""Unified task schema for the AgentBench-Golden dataset.

Every upstream benchmark (SWE-bench family, SWE-Bench++, SWE-bench Pro,
SWE-rebench, NYU CTF / EnIGMA) is normalised into :class:`GoldenTask` so that
one evaluation harness and one code-quality module can run over all domains.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

DOMAINS = (
    "bug_fix",
    "feature_implementation",
    "refactoring",
    "performance",
    "security_fix",
    "frontend_visual",
    "test_generation",
    "offensive_security_ctf",
)

DIFFICULTIES = ("easy", "medium", "hard")

# How a task is judged.
EVAL_TYPES = (
    "fail_to_pass",      # apply model patch, FAIL_TO_PASS must pass, PASS_TO_PASS must stay green
    "test_generation",   # model writes tests: must FAIL on base commit and PASS with gold patch
    "flag_match",        # CTF: submitted flag must equal the hidden flag
)


@dataclass
class GoldenTask:
    task_id: str
    source: str
    source_instance_id: str
    domain: str
    subdomain: str
    eval_type: str
    language: str
    problem_statement: str
    repo: str = ""
    base_commit: str = ""
    hints: str = ""
    gold_patch: str = ""
    test_patch: str = ""
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    difficulty: str = "medium"
    difficulty_source: str = "heuristic"
    created_at: str = ""
    human_validated: bool = False
    domain_confidence: float = 0.0
    domain_evidence: list[str] = field(default_factory=list)
    patch_stats: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    gate_flags: list[str] = field(default_factory=list)
    code_quality: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoldenTask",
    "type": "object",
    "required": [
        "task_id", "source", "source_instance_id", "domain", "subdomain",
        "eval_type", "language", "problem_statement", "difficulty",
    ],
    "properties": {
        "task_id": {"type": "string", "pattern": r"^[a-z_]+::.+$"},
        "source": {"type": "string"},
        "domain": {"enum": list(DOMAINS)},
        "eval_type": {"enum": list(EVAL_TYPES)},
        "difficulty": {"enum": list(DIFFICULTIES)},
        "language": {"type": "string", "minLength": 1},
        "problem_statement": {"type": "string", "minLength": 20},
        "fail_to_pass": {"type": "array", "items": {"type": "string"}},
        "pass_to_pass": {"type": "array", "items": {"type": "string"}},
        "domain_confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "human_validated": {"type": "boolean"},
    },
    "allOf": [
        {
            "if": {"properties": {"eval_type": {"const": "fail_to_pass"}}},
            "then": {"properties": {"gold_patch": {"minLength": 1},
                                    "fail_to_pass": {"minItems": 1}}},
        }
    ],
}
