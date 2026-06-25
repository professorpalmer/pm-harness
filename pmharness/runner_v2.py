from __future__ import annotations

"""Stage 3.5 runner: drive every V2 episode per model, score, persist."""

import time, uuid
from .episode_v2 import EPISODES_V2
from .episode_v2_runner import run_episode_v2
from .scoring_v2 import score_v2
from .ledger import TrajectoryLedgerV2
from .drivers.base import Driver


def run_driver_v2(driver: Driver, ledger: TrajectoryLedgerV2, *, run_id: str) -> list:
    scores=[]
    for ep in EPISODES_V2:
        traj=run_episode_v2(driver, ep)
        s=score_v2(ep, traj)
        ledger.record(run_id, s)
        scores.append(s)
    return scores


def new_v2_run_id() -> str:
    return f"v2_{int(time.time())}_{uuid.uuid4().hex[:6]}"
