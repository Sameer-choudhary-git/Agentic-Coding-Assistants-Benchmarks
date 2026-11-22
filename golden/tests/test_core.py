"""Unit tests for the offline parts of the pipeline (no network)."""
import random

from agentbench.code_quality import analyzers as A
from agentbench.code_quality.scorer import QualityAssessor
from agentbench.diffutil import apply_file_diff, parse_diff, patch_stats
from agentbench.evaluation.harness import judge_flag, judge_test_generation
from agentbench.evaluation.metrics import localization, wilson
from agentbench.gates import apply_gates, is_admitted, solution_leak
from agentbench.difficulty import calibrate, complexity_score
from agentbench.sampler import derive_test_generation, pick_domain, stratified_pick
from agentbench.schema import GoldenTask
from agentbench.taxonomy import classify

ORIG = "def f(x):\n    return x + 1\n\n\ndef g(y):\n    return y\n"
PATCH = """diff --git a/pkg/mod.py b/pkg/mod.py
--- a/pkg/mod.py
+++ b/pkg/mod.py
@@ -1,2 +1,4 @@
 def f(x):
-    return x + 1
+    if x is None:
+        return 0
+    return x + 1
diff --git a/tests/test_mod.py b/tests/test_mod.py
--- a/tests/test_mod.py
+++ b/tests/test_mod.py
@@ -0,0 +1,2 @@
+def test_none():
+    assert f(None) == 0
"""


class FakeFetcher:
    def __init__(self, files):
        self.files = files

    def get(self, repo, commit, path):
        return self.files.get(path)


def _task(**kw):
    base = dict(task_id="swebench_verified::a__b-1", source="swebench_verified", source_instance_id="a__b-1",
                domain="bug_fix", subdomain="logic_error", eval_type="fail_to_pass", language="python",
                problem_statement="Calling f(None) raises TypeError instead of returning 0. " * 4,
                repo="a/b", base_commit="abc", gold_patch=PATCH,
                test_patch="diff --git a/tests/test_mod.py b/tests/test_mod.py\n--- a/tests/test_mod.py\n+++ b/tests/test_mod.py\n@@ -0,0 +1,1 @@\n+x=1\n",
                fail_to_pass=["tests/test_mod.py::test_none"], human_validated=True, domain_confidence=0.9)
    base.update(kw)
    t = GoldenTask(**base)
    t.patch_stats = patch_stats(t.gold_patch)
    return t


GATES = dict(min_problem_chars=50, max_problem_chars=20000, max_patch_changed_lines=600, max_patch_files=12,
             leak_min_line_chars=10, leak_min_matching_lines=2, near_duplicate_jaccard=0.8,
             rebench_max_issue_text_score=1, rebench_max_test_score=1, contamination_cutoff="2024-06-01")


def test_parse_and_apply():
    files = parse_diff(PATCH)
    assert [f.path for f in files] == ["pkg/mod.py", "tests/test_mod.py"]
    assert files[1].is_new is False or files[1].hunks
    new = apply_file_diff(ORIG, files[0])
    assert "if x is None:" in new and new.count("def ") == 2


def test_patch_stats_excludes_tests_from_source():
    ps = patch_stats(PATCH)
    assert ps["source_files"] == 1 and ps["test_files"] == 1 and ps["added"] == 5


def test_classifier_security_and_template_negation():
    sec = classify(source="swe_rebench", problem="Path traversal vulnerability lets attackers read /etc/passwd via ../")
    assert sec.domain == "security_fix" and sec.subdomain == "path_traversal"
    tmpl = classify(source="swe_rebench",
                    problem="- [x] This is not a security vulnerability\nThe parser crashes with a traceback on empty input")
    assert tmpl.domain == "bug_fix"


def test_classifier_feature_and_perf():
    assert classify(source="swe_rebench", problem="Feature request: add support for YAML config files. "
                    "It would be nice to allow users to choose.").domain == "feature_implementation"
    assert classify(source="swe_rebench", problem="Sorting is quadratic time; it takes too long and is a "
                    "performance regression on large inputs").domain == "performance"
    assert classify(source="nyu_ctf", problem="x", labels={"ctf_category": "pwn"}).subdomain == "pwn"


def test_solution_leak_gate():
    leaky = _task(problem_statement="Fix: change it to\n    if x is None:\n        return 0\n    return x + 1\nthat's all, thanks " * 3)
    clean = _task(task_id="swebench_verified::a__b-2", source_instance_id="a__b-2")
    hits, _ = solution_leak(leaky.problem_statement, leaky.gold_patch, 10, 2)
    assert hits >= 2
    apply_gates([leaky, clean], {**GATES, "_source_priority": []})
    assert "solution_leak" in leaky.gate_flags and not is_admitted(leaky)
    assert is_admitted(clean)


def test_duplicate_gate_prefers_priority_source():
    a = _task()
    b = _task(task_id="swebench_plus::a__b-1", source="swebench_plus")
    apply_gates([b, a], {**GATES, "_source_priority": ["swebench_verified", "swebench_plus"]})
    assert "duplicate_instance" in b.gate_flags and is_admitted(a)


def test_stratified_pick_respects_quota_and_repo_cap():
    rng = random.Random(0)
    pool = [_task(task_id=f"s::{i}", source_instance_id=str(i), repo=f"r/{i % 2}",
                  difficulty=["easy", "medium", "hard"][i % 3]) for i in range(40)]
    picked = stratified_pick(pool, 10, {}, rng)
    assert len(picked) == 6  # repo cap of 3 x 2 repos binds before the quota
    filled = pick_domain(pool, 10, {}, rng)  # relaxes the cap to meet the quota
    assert len(filled) == 10 and len({t.task_id for t in filled}) == 10


def test_derive_test_generation():
    d = derive_test_generation(_task())
    assert d.domain == "test_generation" and d.eval_type == "test_generation" and "::testgen::" in d.task_id


def test_difficulty_calibration_monotone():
    small, big = {"changed": 3, "source_files": 1, "hunks": 1}, {"changed": 300, "source_files": 6, "hunks": 20}
    assert complexity_score(big) > complexity_score(small)
    assert calibrate([])["n"] == 0


def test_quality_module_penalises_bad_patch():
    qa = QualityAssessor(FakeFetcher({"pkg/mod.py": ORIG}))
    good = qa.assess("a/b", "abc", PATCH)
    bad_patch = PATCH.replace("+        return 0", "+        print('debug')  # TODO\n+        return eval('0')")
    bad = qa.assess("a/b", "abc", bad_patch, reference_patch=PATCH)
    assert good["quality_score"] >= 95
    assert bad["quality_score"] < good["quality_score"]
    assert bad["smells"].get("debug_statement") and bad["smells"].get("todo_marker")
    assert bad["bandit_new"] or bad["security_patterns"]


def test_diff_smells_language_agnostic():
    r = A.diff_smells(["console.log(x)", "el.innerHTML = userInput", "// eslint-disable-next-line"], "javascript")
    assert r["smells"]["debug_statement"] == 1 and r["smells"]["lint_suppression"] == 1
    assert r["security_patterns"]["dom_xss_sink"] == 1


def test_metrics_and_judges():
    p, lo, hi = wilson(5, 10)
    assert lo < p < hi and p == 0.5
    assert localization(PATCH, PATCH)["f1"] == 1.0
    assert judge_flag(" flag{x} \n", "flag{x}") and not judge_flag("flag{y}", ["flag{x}"])
    r = judge_test_generation({"t1": "FAILED", "t2": "PASSED"}, {"t1": "PASSED", "t2": "PASSED"})
    assert r["resolved"] and r["fail_to_pass"] == ["t1"]


def test_stray_scratch_files_detected():
    stray = PATCH + ("diff --git a/reproduce_issue.py b/reproduce_issue.py\nnew file mode 100644\n"
                     "--- /dev/null\n+++ b/reproduce_issue.py\n@@ -0,0 +1,2 @@\n+from pkg.mod import f\n+print(f(None))\n")
    qa = QualityAssessor(FakeFetcher({"pkg/mod.py": ORIG}))
    r = qa.assess("a/b", "abc", stray)
    assert r["stray_files"] == ["reproduce_issue.py"]
    assert not r["smells"].get("debug_statement")  # scratch prints are not counted twice
    assert r["penalties"]["hygiene"] >= 5



def _app_entry(iid, domain, **kw):
    e = {"instance_id": iid, "domain": domain, "subdomain": "x", "tier": "easy", "repo": "a/b", "source": "s",
         "gate_flags": [], "domain_confidence": 0.9, "gold_quality_score": 95.0, "gold_patch_applies": True,
         "fail_to_pass_count": 1, "pass_to_pass_count": 3, "human_validated": True}
    e.update(kw)
    return e


def test_core_eligibility_rules():
    from agentbench.app_export import core_eligible
    assert core_eligible(_app_entry("a", "bug_fix"))[0]
    assert core_eligible(_app_entry("a", "bug_fix", pass_to_pass_count=0))[1].startswith("no PASS_TO_PASS")
    assert not core_eligible(_app_entry("a", "bug_fix", gate_flags=["solution_hint_partial"]))[0]
    assert not core_eligible(_app_entry("a", "bug_fix", gold_patch_applies=False))[0]
    assert not core_eligible(_app_entry("a", "bug_fix", domain_confidence=0.5))[0]


def test_review_relabels_and_validates_core():
    import pytest
    from agentbench.app_export import apply_review
    entries = [_app_entry("p1", "performance"), _app_entry("p2", "performance"), _app_entry("b1", "bug_fix")]
    review = {"label_corrections": {"p2": {"to": "bug_fix", "why": "not perf"}},
              "core": {"performance": {"p1": "ok"}, "bug_fix": {"p2": "relabelled"}}}
    core = apply_review(entries, review, per_domain=1)
    assert core == {"p1", "p2"} and entries[1]["domain"] == "bug_fix" and entries[1]["original_domain"] == "performance"
    with pytest.raises(ValueError, match="listed under"):
        apply_review([_app_entry("p1", "performance")], {"core": {"bug_fix": {"p1": ""}}}, per_domain=1)
    with pytest.raises(ValueError, match="expected 2"):
        apply_review([_app_entry("p1", "performance")], {"core": {"performance": {"p1": ""}}}, per_domain=2)
