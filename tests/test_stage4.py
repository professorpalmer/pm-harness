"""Stage 4 discriminates: the findings-reader passes; the lazy stopper fails the
inconclusive trap and sequenced episodes. Proves the battery RANKS, unlike V2."""
import pytest
pytestmark = pytest.mark.swarm
from pmharness.episode_s4 import EPISODES_S4
from pmharness.runner_s4 import run_episode_s4
from pmharness.scoring_v2 import score_v2
from pmharness.drivers.stub_s4 import ReaderStub, LazyStub


def _mean(driver):
    scores=[]
    for ep in EPISODES_S4:
        traj=run_episode_s4(driver, ep)
        scores.append(score_v2(ep, traj))
    return scores


def test_reader_beats_lazy_overall():
    reader=_mean(ReaderStub()); lazy=_mean(LazyStub())
    r=sum(s.score for s in reader)/len(reader)
    l=sum(s.score for s in lazy)/len(lazy)
    assert r > l, f"reader {r} should beat lazy {l}"


def test_lazy_fails_inconclusive_trap():
    ep=[e for e in EPISODES_S4 if e.id=="trap_inconclusive"][0]
    lazy=score_v2(ep, run_episode_s4(LazyStub(), ep))
    # lazy stops after 1 swarm; min_swarms=2 -> premature, not efficient
    assert lazy.premature is True
    assert lazy.score < 1.0


def test_reader_passes_inconclusive_trap():
    ep=[e for e in EPISODES_S4 if e.id=="trap_inconclusive"][0]
    r=score_v2(ep, run_episode_s4(ReaderStub(), ep))
    assert r.swarms_run >= 2  # continued past the inconclusive first pass
    assert r.terminated and r.got_terminal=="stop"


def test_reader_does_not_overrun_conclusive_trap():
    ep=[e for e in EPISODES_S4 if e.id=="trap_conclusive"][0]
    r=score_v2(ep, run_episode_s4(ReaderStub(), ep))
    # conclusive after pass 1 -> should stop at exactly 1 swarm
    assert r.swarms_run == 1
    assert r.score == 1.0


def test_sequenced_needs_two_passes():
    ep=[e for e in EPISODES_S4 if e.id=="seq_two_pass"][0]
    r=score_v2(ep, run_episode_s4(ReaderStub(), ep))
    assert r.swarms_run >= 2 and r.terminated
