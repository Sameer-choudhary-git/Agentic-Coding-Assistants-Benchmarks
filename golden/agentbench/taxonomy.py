"""Task-domain taxonomy and classifier.

Classification is evidence-based and transparent: every decision records the
signals that produced it (``domain_evidence``) and a confidence in [0, 1].

Priority order:
 1. Structural source signal (multimodal -> frontend_visual, CTF -> offensive_security_ctf)
 2. Curated source labels (SWE-bench Pro ``issue_specificity``/``issue_categories``,
    SWE-Bench++ ``task_type``)
 3. Keyword + patch-shape scoring over the issue text and gold patch

Security is treated as an *override*: a bug fix that closes a vulnerability is
classified ``security_fix`` because the evaluation concern (secure code) differs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .diffutil import parse_diff, is_test_path

# (pattern, weight). Patterns are matched case-insensitively on issue text.
KEYWORDS: dict[str, list[tuple[str, float]]] = {
    "security_fix": [
        (r"\bcve-\d{4}-\d+", 3.0), (r"\bvulnerab", 2.5), (r"\b(xss|cross[- ]site scripting)\b", 3.0),
        (r"\bcsrf\b", 3.0), (r"\bsql injection\b", 3.0), (r"\b(command|code|header|template) injection\b", 3.0),
        (r"\b(path|directory) traversal\b", 3.0), (r"\bssrf\b", 3.0), (r"\bremote code execution\b", 3.0),
        (r"\bredos\b", 3.0), (r"\bsecurity (issue|fix|vulnerability|advisory|bug|hole)\b", 2.5),
        (r"\b(auth(entication|orization)?) bypass\b", 3.0), (r"\bprivilege escalation\b", 3.0),
        (r"\b(leak(s|ed|ing)?|expos(e|es|ed|ing)) (secret|password|token|credential|api key)", 2.5),
        (r"\bunsafe deserializ", 2.5), (r"\b(open redirect)\b", 3.0), (r"\bsanitiz", 1.0),
        (r"\bdenial[- ]of[- ]service\b", 2.0), (r"\bmalicious\b", 1.0),
    ],
    "performance": [
        (r"\b(performance|perf) (issue|regression|problem|improvement)", 2.5), (r"\bslow(er|ly|ness)?\b", 1.2),
        (r"\bspeed ?up\b", 2.0), (r"\bfaster\b", 1.0), (r"\blatency\b", 1.5), (r"\bmemory (usage|leak|consumption)\b", 2.0),
        (r"\bquadratic (time|complexity|runtime|behaviou?r|blow ?up)\b|\bo\(n\^?2\)|\bo\(n\*\*2\)", 2.5), (r"\boptimi[sz](e|ation)\b", 1.2), (r"\btakes? (too|very) long\b", 2.0),
        (r"\bbottleneck\b", 2.0), (r"\b(cpu|time) (usage|consumption)\b", 1.5), (r"\bbenchmark", 1.0),
    ],
    "refactoring": [
        (r"\brefactor", 2.5), (r"\bclean ?up\b", 1.5), (r"\bdeprecat", 1.2), (r"\bcode quality\b", 2.0),
        (r"\btech(nical)? debt\b", 2.5), (r"\brestructur", 1.5), (r"\bsimplif(y|ies|ication)\b", 1.0),
        (r"\bduplicat(ed|ion) code\b", 2.0), (r"\bextract (method|function|class)\b", 2.0), (r"\brename\b", 0.6),
        (r"\bmodernize\b", 1.5), (r"\btype (hints|annotations)\b", 1.0),
    ],
    "feature_implementation": [
        (r"\bfeature request\b", 3.0), (r"\badd(ing)? support (for|of)\b", 2.5), (r"\bsupport for\b", 1.0),
        (r"\bit would be (nice|great|useful|good)\b", 2.0), (r"\bwould (like|love) to (be able|have|see)\b", 1.5),
        (r"\bnew (option|flag|parameter|argument|feature|api|method|command|endpoint|setting)\b", 2.0),
        (r"\b(enhancement|proposal|suggestion)\b", 1.5), (r"\bimplement(ing|ation)? (a|an|the)? ?new\b", 2.0),
        (r"\bplease add\b", 2.0), (r"\ballow (users?|.{0,20}) to\b", 1.0), (r"\bis there (a|any) way to\b", 1.0),
        (r"\bdescribe the solution you'?d like\b", 3.0), (r"\bmotivation\b", 0.8),
    ],
    "bug_fix": [
        (r"\bbug\b", 1.5), (r"\btraceback\b", 2.0), (r"\bexception\b", 1.0), (r"\b(crash(es|ed)?|segfault|panic)\b", 2.0),
        (r"\b(incorrect|wrong|unexpected)(ly)?\b", 1.0), (r"\bfails?\b|\bfailing\b", 0.8), (r"\bregression\b", 1.5),
        (r"\b(doesn'?t|does not|isn'?t|is not) work", 1.5), (r"\bbroken\b", 1.2), (r"\berror\b", 0.6),
        (r"\bexpected (behaviou?r|result|output)\b", 1.5), (r"\bsteps to reproduce\b", 1.5), (r"\breproduc", 0.8),
        (r"\bactual (behaviou?r|result|output)\b", 1.5),
    ],
}
_COMPILED = {d: [(re.compile(p, re.I), w) for p, w in pats] for d, pats in KEYWORDS.items()}

PRO_MAP = {  # SWE-bench Pro issue_specificity labels
    "core_feat": "feature_implementation", "integration_feat": "feature_implementation",
    "api_feat": "feature_implementation", "ui_ux_feat": "feature_implementation",
    "customization_feat": "feature_implementation", "dev_ops_enh": "feature_implementation",
    "major_bug": "bug_fix", "minor_bug": "bug_fix", "edge_case_bug": "bug_fix", "ui_ux_bug": "bug_fix",
    "integration_bug": "bug_fix", "data_bug": "bug_fix", "compatibility_bug": "bug_fix",
    "regression_bug": "bug_fix", "critical_bug": "bug_fix", "performance_bug": "performance",
    "security_bug": "security_fix", "security_enh": "security_fix", "security_feat": "security_fix",
    "performance_enh": "performance", "performance_feat": "performance",
    "refactoring_enh": "refactoring", "code_quality_enh": "refactoring", "technical_debt_enh": "refactoring",
    "accessibility_enh": "feature_implementation", "documentation_enh": "refactoring",
}
PLUSPLUS_MAP = {
    "bugfix": "bug_fix", "bug-report": "bug_fix", "feature-request": "feature_implementation",
    "performance-issue": "performance", "documentation": "refactoring",
}


@dataclass
class Classification:
    domain: str
    subdomain: str
    confidence: float
    evidence: list[str]


_CODE_BLOCK = re.compile(r"```.*?```|`[^`\n]+`", re.S)
_URL = re.compile(r"https?://\S+|www\.\S+")
_TEMPLATE = re.compile(
    r"^\s*[-*]\s*\[[ xX]\].*$"                         # checklists
    r"|^.*\b(not a security|security vulnerabilit(y|ies) should|report (it|security)[^\n]* privately"
    r"|security policy|security@)\b.*$"                # template boilerplate about where to report
    r"|^\s*(Traceback|File \"|\s+at )\S*.*$",          # stack frames
    re.M | re.I)
STRONG_SECURITY = re.compile(r"cve-|vulnerab|xss|cross[- ]site|injection|traversal|ssrf|remote code|redos|bypass"
                             r"|privilege|deserializ|open redirect", re.I)


def prose(text: str) -> str:
    """Issue text with code, URLs and template boilerplate removed."""
    t = _CODE_BLOCK.sub(" ", text or "")
    t = _URL.sub(" ", t)
    return _TEMPLATE.sub(" ", t)


def keyword_scores(text: str) -> dict[str, tuple[float, list[str]]]:
    out = {}
    clean = prose(text)
    for dom, pats in _COMPILED.items():
        score, hits = 0.0, []
        for rx, w in pats:
            # bug evidence such as tracebacks lives in code blocks: search raw text for it
            m = rx.search(text if dom == "bug_fix" else clean)
            if m:
                score += w
                hits.append(m.group(0).lower())
        out[dom] = (score, hits)
    return out


def patch_shape_signal(patch: str) -> tuple[str | None, str]:
    """Infer intent from the gold patch: pure additions of new defs suggest a feature."""
    files = [f for f in parse_diff(patch) if not is_test_path(f.path)]
    if not files:
        return None, ""
    added = [l for f in files for l in f.added]
    removed = [l for f in files for l in f.removed]
    new_defs = sum(bool(re.match(r"\s*(def |class |func |fn |pub fn |public |export (function|class|const))", l)) for l in added)
    if any(f.is_new for f in files) and new_defs >= 1:
        return "feature_implementation", f"patch adds new file(s) with {new_defs} new definitions"
    if new_defs >= 3 and len(removed) <= len(added) * 0.15:
        return "feature_implementation", f"patch is additive with {new_defs} new definitions"
    return None, ""


def classify(*, source: str, problem: str, patch: str = "", labels: dict | None = None) -> Classification:
    labels = labels or {}
    text = problem or ""
    kw = keyword_scores(text)
    sec_score, sec_hits = kw["security_fix"]

    # 1. structural
    if source == "nyu_ctf":
        cat = labels.get("ctf_category", "misc")
        return Classification("offensive_security_ctf", cat, 1.0, [f"NYU CTF / EnIGMA challenge category={cat}"])
    if source == "swebench_multimodal":
        return Classification("frontend_visual", "visual_issue", 0.95,
                              ["SWE-bench Multimodal: issue contains screenshots / visual spec"])

    ev: list[str] = []
    label_domain = None
    # 2. curated labels
    if source == "swebench_pro" and labels.get("issue_specificity"):
        mapped = [PRO_MAP[x] for x in labels["issue_specificity"] if x in PRO_MAP]
        if mapped:
            # Pro often co-labels a task (e.g. major_bug + refactoring_enh). Break ties by
            # what is being *fixed*: a bug/vulnerability label dominates an enhancement label.
            precedence = ["security_fix", "bug_fix", "performance", "feature_implementation", "refactoring"]
            label_domain = max(set(mapped), key=lambda d: (mapped.count(d), -precedence.index(d)))
            if "bug_fix" in mapped and label_domain == "refactoring":
                label_domain = "bug_fix"
            ev.append(f"SWE-bench Pro label {labels['issue_specificity']}")
        if "security_knowledge" in labels.get("issue_categories", []) or \
           "authentication_authorization_knowledge" in labels.get("issue_categories", []):
            sec_score += 1.5
            sec_hits.append("pro:security_knowledge")
    if source == "swebench_plusplus" and labels.get("task_type") in PLUSPLUS_MAP:
        label_domain = PLUSPLUS_MAP[labels["task_type"]]
        ev.append(f"SWE-Bench++ task_type={labels['task_type']}")
        if labels.get("repo_type") == "security":
            sec_score += 1.0
            sec_hits.append("pp:repo_type=security")

    # security override (strong evidence only: score >= 3 and either >= 2 distinct
    # signals or one unambiguous vulnerability term)
    strong = [h for h in sec_hits if STRONG_SECURITY.search(h)]
    if sec_score >= 3.0 and strong:
        return Classification("security_fix", _sec_sub(text), min(1.0, 0.5 + sec_score / 10),
                              ev + [f"security keywords: {sec_hits}"])

    if label_domain:
        # labels are curated, but cross-check against keywords
        conf = 0.85
        best_kw = max(("performance", "refactoring", "feature_implementation", "bug_fix"),
                      key=lambda d: kw[d][0])
        if best_kw != label_domain and kw[best_kw][0] >= 4.0 and kw[label_domain][0] < 1.0:
            conf = 0.6
            ev.append(f"keywords disagree (suggest {best_kw}: {kw[best_kw][1]})")
        return Classification(label_domain, _sub(label_domain, text), conf, ev)

    # 3. keyword + patch shape
    shape_dom, shape_ev = patch_shape_signal(patch)
    scores = {d: kw[d][0] for d in ("performance", "refactoring", "feature_implementation", "bug_fix")}
    if shape_dom:
        scores[shape_dom] += 1.5
        ev.append(shape_ev)
    # issues with no signal at all default to bug_fix (SWE-bench prior: ~85% bug reports)
    scores["bug_fix"] += 0.5
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, s1 = ranked[0]
    # minimum margins: non-bug domains need clear evidence
    if best in ("performance", "refactoring") and (s1 < 2.5 or s1 <= scores["bug_fix"]):
        best, s1 = "bug_fix" if scores["bug_fix"] >= scores["feature_implementation"] else "feature_implementation", max(scores["bug_fix"], scores["feature_implementation"])
    if best == "feature_implementation" and (s1 < 2.0 or s1 <= scores["bug_fix"]):
        best, s1 = "bug_fix", scores["bug_fix"]
    total = sum(max(v, 0) for v in scores.values()) or 1.0
    conf = round(min(0.95, 0.35 + 0.6 * (s1 / total)), 3)
    ev.append(f"keyword scores {({k: round(v, 1) for k, v in scores.items()})}; hits={kw[best][1][:5]}")
    return Classification(best, _sub(best, text), conf, ev)


def _sec_sub(text: str) -> str:
    t = text.lower()
    for key, sub in [("xss", "xss"), ("cross-site scripting", "xss"), ("csrf", "csrf"), ("injection", "injection"),
                     ("traversal", "path_traversal"), ("ssrf", "ssrf"), ("redos", "redos"),
                     ("denial", "dos"), ("auth", "authz_authn"), ("deserial", "deserialization"),
                     ("redirect", "open_redirect"), ("token", "secret_exposure"), ("password", "secret_exposure")]:
        if key in t:
            return sub
    return "vulnerability"


def _sub(domain: str, text: str) -> str:
    t = text.lower()
    if domain == "security_fix":
        return _sec_sub(text)
    if domain == "bug_fix":
        if re.search(r"traceback|exception|raise[sd]?\b|error:", t):
            return "crash_exception"
        if re.search(r"regression", t):
            return "regression"
        return "logic_error"
    if domain == "feature_implementation":
        if re.search(r"\b(api|endpoint|parameter|argument|option|flag)\b", t):
            return "api_extension"
        return "new_capability"
    if domain == "performance":
        return "memory" if "memory" in t else "runtime"
    if domain == "refactoring":
        return "deprecation" if "deprecat" in t else "restructuring"
    return domain
