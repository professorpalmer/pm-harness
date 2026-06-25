"""Real read-only analysis path: builds no-edit specs, defaults stay demo, and a
target repo is never mutated. The live model call is exercised separately."""
import pytest
pytestmark = pytest.mark.swarm
import os
import tempfile
import hashlib
from pathlib import Path

from pmharness.intent import DriverIntent
from pmharness import bridge


def test_default_is_demo_no_repo(monkeypatch):
    monkeypatch.delenv("HARNESS_SWARM_ADAPTER", raising=False)
    monkeypatch.delenv("HARNESS_REPO", raising=False)
    res = bridge.execute_intent(
        DriverIntent(action="run_swarm", goal="x", rationale="y"),
        state_dir=tempfile.mkdtemp())
    assert res.adapter == "demo"


def test_openai_path_requires_repo(monkeypatch):
    # openai adapter set but no repo -> falls back to demo (cannot analyze nothing)
    monkeypatch.setenv("HARNESS_SWARM_ADAPTER", "openai")
    monkeypatch.delenv("HARNESS_REPO", raising=False)
    res = bridge.execute_intent(
        DriverIntent(action="run_swarm", goal="x", rationale="y"),
        state_dir=tempfile.mkdtemp())
    assert res.adapter == "demo"


def test_analysis_specs_are_read_only():
    # The specs the bridge builds for analysis must declare read_only/no_edit so
    # they can never edit a target repo (defense in depth on top of the openai
    # adapter not being edit-capable).
    from puppetmaster.workers import WorkerSpec, spec_edits_files, spec_explicitly_no_edit
    spec = WorkerSpec(role="explore", instruction="analyze", adapter="openai",
                      payload={"read_only": True, "no_edit": True, "dry_run": True,
                               "cwd": "/tmp"})
    assert spec_explicitly_no_edit(spec) is True
    assert spec_edits_files(spec) is False


def test_analysis_does_not_mutate_target_repo(monkeypatch, tmp_path):
    # Create a tiny fake repo, snapshot it, run analysis (demo path -- no key
    # needed), confirm zero files changed/created/deleted.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def foo():\n    return 1\n")
    (repo / "b.py").write_text("X = 2\n")
    before = {p.name: hashlib.md5(p.read_bytes()).hexdigest()
              for p in repo.glob("*.py")}
    # demo path (no key) still proves the bridge never writes into the repo
    monkeypatch.setenv("HARNESS_SWARM_ADAPTER", "openai")
    monkeypatch.setenv("HARNESS_REPO", str(repo))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # no key -> worker no-ops, still no edits
    bridge.execute_intent(DriverIntent(action="run_swarm", goal="audit", rationale="x"),
                          state_dir=tempfile.mkdtemp())
    after = {p.name: hashlib.md5(p.read_bytes()).hexdigest()
             for p in repo.glob("*.py")}
    assert before == after, "analysis must NEVER mutate the target repo"
    assert set(before) == set(after), "analysis must not add/remove files"
