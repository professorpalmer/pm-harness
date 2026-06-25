"""Fully-Auto (run_auto): governor bounds it, codegraph-gate refuses unindexed
analysis, and it stops when the pilot is done. The autonomy safety proof."""
import tempfile
from harness.config import HarnessConfig
from harness.conversation import ConversationalSession
from harness.autobudget import AutoBudget
from pmharness.drivers.openai_compat import DriverResponse


class _NeverDonePilot:
    """Always fires another swarm -- to prove the GOVERNOR stops it, not the pilot."""
    name = "neverdone"
    def complete(self, prompt, *, system=None):
        return DriverResponse(
            text='{"say":"still digging","actions":[{"kind":"run_swarm","goal":"keep going"}]}',
            tokens_out=10, latency_ms=1.0)


class _DonePilot:
    """Fires one swarm then declares done -- to prove the loop stops cleanly."""
    name = "done"
    def __init__(self): self.n = 0
    def complete(self, prompt, *, system=None):
        self.n += 1
        if self.n == 1:
            t = '{"say":"checking","actions":[{"kind":"run_swarm","goal":"look"}]}'
        else:
            t = '{"say":"Objective met.","actions":[]}'
        return DriverResponse(text=t, tokens_out=10, latency_ms=1.0)


def test_auto_refuses_unindexed_analysis(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()  # no .codegraph
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp(),
                        repo=str(repo), swarm_adapter="openai")
    s = ConversationalSession(cfg)
    s.pilot = _DonePilot()
    events = list(s.run_auto("audit it", AutoBudget(max_swarms=5)))
    assert events[0].kind == "auto_halt"
    assert "no .codegraph index" in events[0].data["reason"]


def test_auto_governor_stops_neverending_pilot():
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    s = ConversationalSession(cfg)
    s.pilot = _NeverDonePilot()
    # demo adapter (no repo) -> no codegraph gate; governor must stop it
    events = list(s.run_auto("dig forever", AutoBudget(max_swarms=3)))
    halts = [e for e in events if e.kind == "auto_halt"]
    assert halts, "governor must halt a never-ending pilot"
    assert "ceiling" in halts[-1].data["reason"] or "stall" in halts[-1].data["reason"]


def test_auto_stops_when_pilot_done():
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    s = ConversationalSession(cfg)
    s.pilot = _DonePilot()
    events = list(s.run_auto("quick check", AutoBudget(max_swarms=20)))
    halts = [e for e in events if e.kind == "auto_halt"]
    assert halts and "objective met" in halts[-1].data["reason"]


def test_auto_killswitch(tmp_path):
    ks = tmp_path / "STOP"; ks.write_text("x")  # pre-tripped
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    s = ConversationalSession(cfg)
    s.pilot = _NeverDonePilot()
    events = list(s.run_auto("go", AutoBudget(max_swarms=99, killswitch_path=str(ks))))
    halts = [e for e in events if e.kind == "auto_halt"]
    assert halts and "killswitch" in halts[-1].data["reason"]
