"""Analysis benchmark scoring + the unindexed-repo guard (the bug the bench caught)."""
import os
import tempfile
import pytest
from pmharness.analysis_bench import ANALYSIS_QUESTIONS, score_analysis, AnalysisQ
from pmharness import bridge


def test_scoring_hit_no_fab_is_full():
    q = AnalysisQ(id="x", prompt="p", must_contain=("drive_with_repair",),
                  must_not_contain=("repair_intent",))
    r = score_analysis(q, "the function is drive_with_repair")
    assert r["score"] == 1.0 and r["hit"] and not r["fab"]


def test_scoring_fabrication_penalized():
    q = AnalysisQ(id="x", prompt="p", must_contain=("drive_with_repair",),
                  must_not_contain=("repair_intent",))
    # wrong name only -> fabrication, no hit -> 0.0
    r = score_analysis(q, "the function is repair_intent")
    assert r["score"] == 0.0 and r["fab"] and not r["hit"]


def test_scoring_silent_is_quarter():
    q = AnalysisQ(id="x", prompt="p", must_contain=("drive_with_repair",),
                  must_not_contain=("repair_intent",))
    r = score_analysis(q, "I could not determine the function name")
    assert r["score"] == 0.25


def test_questions_have_ground_truth():
    for q in ANALYSIS_QUESTIONS:
        assert q.must_contain, f"{q.id} has no ground truth"


def test_unindexed_repo_warns(monkeypatch, tmp_path, capsys):
    repo = tmp_path / "norepo"; repo.mkdir()
    monkeypatch.delenv("HARNESS_REQUIRE_CODEGRAPH", raising=False)
    bridge._warn_if_unindexed(str(repo))
    err = capsys.readouterr().err
    assert "no .codegraph index" in err and "BLIND" in err


def test_unindexed_repo_hard_fails_when_required(monkeypatch, tmp_path):
    repo = tmp_path / "norepo"; repo.mkdir()
    monkeypatch.setenv("HARNESS_REQUIRE_CODEGRAPH", "1")
    with pytest.raises(RuntimeError):
        bridge._warn_if_unindexed(str(repo))


def test_indexed_repo_no_warning(monkeypatch, tmp_path, capsys):
    repo = tmp_path / "repo"; (repo / ".codegraph").mkdir(parents=True)
    bridge._warn_if_unindexed(str(repo))
    assert capsys.readouterr().err == ""
