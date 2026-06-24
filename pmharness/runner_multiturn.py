from __future__ import annotations

"""Multi-turn eval runner: drive every episode per model, score the trajectory,
persist to the TrajectoryLedger."""

import time, uuid
from .episode_battery import EPISODES
from .episode import run_episode
from .scoring_multiturn import score_trajectory
from .ledger import TrajectoryLedger
from .drivers.base import Driver


def run_driver_multiturn(driver: Driver, ledger: TrajectoryLedger, *, run_id: str) -> list:
    scores = []
    for ep in EPISODES:
        traj = run_episode(driver, ep)
        ts = score_trajectory(ep, traj)
        ledger.record(run_id, ts)
        scores.append(ts)
    return scores


def new_mt_run_id() -> str:
    return f"mt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
