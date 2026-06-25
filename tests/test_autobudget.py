"""AutoBudget governor: every ceiling must provably HALT. These tests are the
safety proof -- they run BEFORE any autonomy depends on the governor."""
import os
import time
import tempfile
from harness.autobudget import AutoBudget


def test_proceeds_when_under_all_ceilings():
    b = AutoBudget(max_tokens=1000, max_seconds=100, max_swarms=10).start()
    assert b.check() is None


def test_token_ceiling_halts():
    b = AutoBudget(max_tokens=100).start()
    b.add_tokens(150)
    assert "token ceiling" in (b.check() or "")


def test_swarm_ceiling_halts():
    b = AutoBudget(max_swarms=2).start()
    b.add_swarm(); b.add_swarm()
    assert "swarm ceiling" in (b.check() or "")


def test_time_ceiling_halts():
    b = AutoBudget(max_seconds=0).start()
    time.sleep(0.01)
    assert "time ceiling" in (b.check() or "")


def test_killswitch_halts(tmp_path):
    ks = tmp_path / "STOP"
    b = AutoBudget(max_tokens=10**9, killswitch_path=str(ks)).start()
    assert b.check() is None       # not yet
    ks.write_text("stop")
    assert "killswitch" in (b.check() or "")


def test_stall_halts():
    b = AutoBudget(max_idle_steps=2).start()
    b.note_findings(0); assert b.check() is None
    b.note_findings(0); assert "stall" in (b.check() or "")


def test_findings_reset_idle():
    b = AutoBudget(max_idle_steps=2).start()
    b.note_findings(0)
    b.note_findings(3)   # progress -> reset
    assert b.idle_steps == 0
    assert b.check() is None


def test_halt_is_sticky():
    b = AutoBudget(max_tokens=10).start()
    b.add_tokens(20)
    r1 = b.check()
    b.tokens_used = 0   # even if counters reset, a halt stays halted
    assert b.check() == r1


def test_from_env(monkeypatch):
    monkeypatch.setenv("HARNESS_AUTO_MAX_TOKENS", "5000")
    monkeypatch.setenv("HARNESS_AUTO_MAX_SWARMS", "7")
    b = AutoBudget.from_env()
    assert b.max_tokens == 5000 and b.max_swarms == 7


def test_snapshot_shape():
    b = AutoBudget(max_tokens=100).start()
    b.add_tokens(40); b.add_swarm()
    s = b.snapshot()
    assert s["tokens_used"] == 40 and s["swarms_used"] == 1 and s["halted"] is None
