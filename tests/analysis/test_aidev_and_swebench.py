"""Tests for the AIDev secondary analysis and the SWE-bench pilot tooling, on synthetic data only."""

import json
import subprocess

import pandas as pd
import pytest

from analysis.aidev import aidev_analysis as aidev
from swebench_pilot import pilot


def synthetic_aidev():
    rows, types = [], []
    pid = 0
    spec = {  # (agent, type): (closed, merged)
        ("openai_codex", "docs"): (40, 36),
        ("openai_codex", "fix"): (40, 30),
        ("copilot", "docs"): (20, 12),
        ("copilot", "fix"): (20, 6),
        ("claude_code", "docs"): (12, 11),
        ("cursor", "fix"): (5, 4),
    }
    for (agent, t), (closed, merged) in spec.items():
        for k in range(closed):
            pid += 1
            rows.append({"id": pid, "agent": agent, "state": "closed", "merged_at": "2025-07-01" if k < merged else None})
            types.append({"id": pid, "type": t})
    rows.append({"id": 999, "agent": "copilot", "state": "open", "merged_at": None})  # open PRs are excluded
    return pd.DataFrame(rows), pd.DataFrame(types)


def test_prepare_keeps_closed_prs_and_labels_agents():
    prs, types = synthetic_aidev()
    df = aidev.prepare(prs, types)
    assert len(df) == 137
    assert set(df["agent"]) == {"OpenAI Codex", "GitHub Copilot", "Claude Code", "Cursor"}
    assert df["merged"].sum() == 36 + 30 + 12 + 6 + 11 + 4


def test_acceptance_tables_and_wilson_bounds():
    df = aidev.prepare(*synthetic_aidev())
    t = aidev.acceptance_table(df, ["agent", "type"])
    row = t[(t["agent"] == "GitHub Copilot") & (t["type"] == "fix")].iloc[0]
    assert row["n"] == 20 and row["merged"] == 6 and row["rate"] == pytest.approx(0.3)
    assert 0 < row["ci_low"] < 0.3 < row["ci_high"] < 1
    assert aidev.wilson(0, 0) == (None, None)
    assert aidev.wilson(5, 5)[1] == 1.0


def test_chi_square_skips_small_cells_and_applies_holm():
    df = aidev.prepare(*synthetic_aidev())
    tests = aidev.chi_square_by_type(df, aidev.STUDY_AGENTS)
    assert set(tests["type"]) == {"docs", "fix"}  # Cursor's 5 fix PRs are below MIN_CELL
    assert (tests["p_holm"] >= tests["p_value"]).all()


def test_analyze_writes_outputs(tmp_path):
    df = aidev.prepare(*synthetic_aidev())
    summary = aidev.analyze(df, tmp_path)
    for f in ["acceptance_by_agent.csv", "acceptance_by_agent_type.csv", "chi_square_by_type.csv", "aidev_table.tex", "aidev_heatmap.png"]:
        assert (tmp_path / f).exists(), f
    assert summary["closed_prs"] == 137
    assert summary["largest_task_type_gap"]["high"] == "docs"
    tex = (tmp_path / "aidev_table.tex").read_text()
    assert "\\textcolor{gray}{80.0}" in tex  # Cursor fix, n=5


def test_missing_column_is_reported():
    with pytest.raises(KeyError, match="merged_at"):
        aidev.normalise_columns(pd.DataFrame({"id": [1], "agent": ["x"], "state": ["closed"]}), ["id", "agent", "state", "merged_at"])


def fake_rows():
    diffs = ["<15 min fix", "15 min - 1 hour", "1-4 hours"]
    return [
        {
            "instance_id": f"org__repo{i % 4}-{i}",
            "repo": f"org/repo{i % 4}",
            "base_commit": f"{i:040x}",
            "difficulty": diffs[i % 3],
            "problem_statement": f"Issue {i}",
        }
        for i in range(30)
    ]


def test_selection_is_seeded_stratified_and_spread_across_repos():
    a = pilot.select_instances(fake_rows(), 9, seed=7)
    b = pilot.select_instances(fake_rows(), 9, seed=7)
    assert [r["instance_id"] for r in a] == [r["instance_id"] for r in b]
    assert {r["difficulty"] for r in a} == {"<15 min fix", "15 min - 1 hour", "1-4 hours"}
    assert sum(r["difficulty"] == "<15 min fix" for r in a) == 3
    assert len({r["repo"] for r in a}) == 4
    assert [r["instance_id"] for r in pilot.select_instances(fake_rows(), 9, seed=8)] != [r["instance_id"] for r in a]
    with pytest.raises(ValueError):
        pilot.select_instances(fake_rows(), 0, seed=1)


def test_manifest_detects_edits(tmp_path):
    path = tmp_path / "m.json"
    pilot.write_manifest(path, [pilot.manifest_entry(r) for r in fake_rows()[:2]], seed=1)
    assert len(pilot.read_manifest(path)["instances"]) == 2
    data = json.loads(path.read_text())
    data["instances"][0]["problem_statement"] = "tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        pilot.read_manifest(path)


def test_prepare_and_collect_produce_harness_predictions(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()

    def g(*a):
        cmd = ["git", "-c", "user.email=t@t", "-c", "user.name=t", *a]
        return subprocess.run(cmd, cwd=upstream, check=True, capture_output=True, text=True).stdout

    g("init", "-q")
    (upstream / "mod.py").write_text("def f():\n    return 1\n")
    g("add", ".")
    g("commit", "-qm", "base")
    base = g("rev-parse", "HEAD").strip()
    entry = pilot.manifest_entry({"instance_id": "x__y-1", "repo": "x/y", "base_commit": base, "problem_statement": "f should return 2"})
    manifest = {"instances": [entry, {**entry, "instance_id": "x__y-2"}]}
    root = tmp_path / "ws"
    pilot.prepare({"instances": [entry]}, "codex", root, 30, clone_url=str(upstream))
    ws = root / "codex" / "x__y-1"
    assert "f should return 2" in (ws / "PILOT_TASK.md").read_text()
    (ws / "mod.py").write_text("def f():\n    return 2\n")
    (ws / "new.py").write_text("X = 1\n")
    preds = pilot.collect(manifest, "codex", root)
    assert preds[0]["model_name_or_path"] == "codex"
    assert "+    return 2" in preds[0]["model_patch"] and "new.py" in preds[0]["model_patch"]
    assert "PILOT_TASK" not in preds[0]["model_patch"]
    assert preds[1]["model_patch"] == ""  # missing workspace -> empty patch, still submitted


def test_summarize_reads_harness_reports(tmp_path):
    (tmp_path / "codex.pilot1.json").write_text(
        json.dumps({"submitted_instances": 4, "resolved_ids": ["a", "b"], "empty_patch_ids": ["c"], "error_ids": []})
    )
    (tmp_path / "other.json").write_text("{}")
    rows = pilot.summarize(list(tmp_path.glob("*.json")))
    assert rows == [
        {
            "assistant": "codex",
            "submitted": 4,
            "resolved": 2,
            "empty_patch": 1,
            "error": 0,
            "resolve_rate": 0.5,
            "report": "codex.pilot1.json",
        }
    ]


def test_select_by_ids_keeps_order_and_rejects_unknown_ids():
    rows = fake_rows()
    cands = [{"instance_id": rows[5]["instance_id"], "tier": "hard"}, {"instance_id": rows[1]["instance_id"], "tier": "easy"}]
    got = pilot.select_by_ids(rows, cands)
    assert [g["instance_id"] for g in got] == [rows[5]["instance_id"], rows[1]["instance_id"]]
    assert got[0]["tier"] == "hard" and pilot.manifest_entry(got[0])["tier"] == "hard"
    with pytest.raises(ValueError, match="not in"):
        pilot.select_by_ids(rows, [{"instance_id": "nope__nope-1"}])


def synthetic_snapshot():
    from analysis.swebench import verified_analysis as va

    ids = [f"org__lib-{i}" for i in range(va.N_VERIFIED - 10)] + [f"other__pkg-{i}" for i in range(10)]
    subs = []
    for k, (date, solved, model, agent) in enumerate(
        [("20240101", 100, "m1", "A"), ("20240601", 300, "m1", "B"), ("20250101", 250, "m2", "A"), ("20250601", 400, "m2", "C")]
    ):
        resolved = list(range(solved))
        by_repo = {
            "org/lib": {"resolved": sum(1 for i in resolved if i < 490), "total": 490},
            "other/pkg": {"resolved": sum(1 for i in resolved if i >= 490), "total": 10},
        }
        by_time = {"2020": {"resolved": solved // 2, "total": 250}, "2022": {"resolved": solved - solved // 2, "total": 250}}
        subs.append(
            {"folder": f"{date}_x{k}", "date": date, "name": f"{agent}+{model}", "model": model, "agent": agent,
             "resolved": resolved, "by_repo": by_repo, "by_time": by_time}
        )  # fmt: skip
    skipped = [{"folder": "s", "name": "Copilot coding agent", "agent": None, "model": None, "reason": "no results files"}]
    return {"source": "test", "commit": "abc1234567", "instances": ids, "submissions": subs, "skipped": skipped}


def test_verified_analysis_on_synthetic_snapshot(tmp_path):
    from analysis.swebench import verified_analysis as va

    res = va.analyze(synthetic_snapshot(), tmp_path, k=2, pilot_n=6, seed=1)
    assert [t["resolve_rate"] for t in res["trajectory"]] == [0.2, 0.6, 0.8]
    bands = {b["band"]: b["instances"] for b in res["hardness_bands"]}
    assert bands["never solved"] == 100 and sum(bands.values()) == 500
    assert res["by_repo"][0] == {"repo": "org/lib", "instances": 490, "top_mean_rate": round(700 / 980, 4)}
    assert {s["model"]: s["spread_pp"] for s in res["scaffold_spread"]} == {"m1": 40.0, "m2": 30.0}
    assert res["products"]["product_entries"]["GitHub Copilot"] == ["Copilot coding agent"]
    tiers = [c["tier"] for c in res["pilot_candidates"]]
    assert tiers.count("easy") == tiers.count("medium") == tiers.count("hard") == 2
    assert all(c["solved_by"] > 0 for c in res["pilot_candidates"])
    assert va.pilot_candidates(res["hardness"], 6, 1) == va.pilot_candidates(res["hardness"], 6, 1)
    for f in ["summary.json", "instance_hardness.csv", "swebench_table.tex", "swebench_verified.png", "swebench_verified.pdf"]:
        assert (tmp_path / f).exists()
    assert va.repo_of("scikit-learn__scikit-learn-12682") == "scikit-learn/scikit-learn"
