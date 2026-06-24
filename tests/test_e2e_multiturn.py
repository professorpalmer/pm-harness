"""Stage 3 E2E: multi-turn stub oracle drives real Puppetmaster across episodes,
trajectory scoring, ledger persist. Fully offline, no keys."""
import tempfile
from pathlib import Path

from pmharness.registry import build
from pmharness.episode import run_episode, MAX_TURNS
from pmharness.episode_battery import EPISODES
from pmharness.scoring_multiturn import score_trajectory
from pmharness.ledger import TrajectoryLedger
from pmharness.runner_multiturn import run_driver_multiturn, new_mt_run_id


def test_single_episode_terminates_and_grounds():
    drv = build("stub-oracle-mt")
    ep = [e for e in EPISODES if e.id == "invest_then_stop"][0]
    traj = run_episode(drv, ep)
    assert traj.terminated
    assert traj.terminal_action == "stop"
    assert traj.swarms_run >= 1
    # the loop fed real Puppetmaster artifacts back and the driver concluded
    assert any(t.executed and t.executed.num_artifacts > 0 for t in traj.turns)
    ts = score_trajectory(ep, traj)
    assert ts.grounded is True
    assert ts.score == 1.0


def test_trivial_episode_zero_swarms():
    drv = build("stub-oracle-mt")
    ep = [e for e in EPISODES if e.id == "trivial_answer"][0]
    traj = run_episode(drv, ep)
    assert traj.terminal_action == "answer"
    assert traj.swarms_run == 0
    ts = score_trajectory(ep, traj)
    assert ts.score == 1.0


def test_already_done_zero_swarms_stop():
    drv = build("stub-oracle-mt")
    ep = [e for e in EPISODES if e.id == "already_done"][0]
    traj = run_episode(drv, ep)
    assert traj.terminal_action == "stop"
    assert traj.swarms_run == 0


def test_full_multiturn_battery_oracle_perfect():
    drv = build("stub-oracle-mt")
    led = TrajectoryLedger(Path(tempfile.mkdtemp(prefix="pmh-mt-")) / "l.sqlite")
    rid = new_mt_run_id()
    scores = run_driver_multiturn(drv, led, run_id=rid)
    assert len(scores) == len(EPISODES)
    mean = sum(s.score for s in scores) / len(scores)
    assert mean == 1.0, f"oracle should be perfect, got {mean}"
    summ = led.summary(rid)
    assert summ[0]["avg_score"] == 100.0
    led.close()


def test_no_infinite_loops():
    """Every episode must terminate within the turn guard."""
    drv = build("stub-oracle-mt")
    for ep in EPISODES:
        traj = run_episode(drv, ep)
        assert len(traj.turns) <= MAX_TURNS
