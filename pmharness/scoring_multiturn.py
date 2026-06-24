from __future__ import annotations

"""Trajectory scoring -- measures multi-turn driving quality, the thing
single-turn cannot see.

Components (all objective):
  terminated:     reached a terminal action within the turn guard (no infinite loop)
  correct_action: terminal action matched the episode's expected terminal
  efficient:      swarms_run within [min_swarms, max_swarms] (no waste, no premature stop)
  all_valid:      every turn emitted a valid DriverIntent
  grounded:       for episodes that ran >=1 swarm, the final stop rationale
                  references the artifacts (cheap textual grounding check)
  score:          composite 0..1
"""

from dataclasses import dataclass, asdict
from typing import Optional

from .episode_battery import Episode
from .episode import Trajectory


@dataclass
class TrajectoryScore:
    episode_id: str
    model: str
    terminated: bool
    correct_action: bool
    efficient: bool
    all_valid: bool
    grounded: Optional[bool]
    swarms_run: int
    turns: int
    score: float
    expect_terminal: str
    got_terminal: Optional[str]
    total_tokens_out: int
    total_latency_ms: float
    error: str = ""

    def to_row(self) -> dict:
        return asdict(self)


def _grounded(traj: Trajectory) -> Optional[bool]:
    if traj.swarms_run < 1:
        return None
    # find the last terminal turn's rationale and any artifact headlines seen
    rationale = ""
    headlines = []
    for t in traj.turns:
        if t.executed:
            headlines += [a["headline"].lower() for a in t.executed.artifacts]
        if t.intent and t.intent.action in ("stop", "answer"):
            rationale = (t.intent.rationale or "").lower()
    if not rationale:
        return False
    # grounded if rationale shares a meaningful token with any artifact headline,
    # or references the act of investigation/findings explicitly
    cue = any(w in rationale for w in
              ("artifact", "finding", "swarm", "investigat", "audit", "establish",
               "identified", "found", "analysis", "risk"))
    overlap = any(
        any(tok in head for tok in rationale.split() if len(tok) > 4)
        for head in headlines
    )
    return bool(cue or overlap)


def score_trajectory(ep: Episode, traj: Trajectory) -> TrajectoryScore:
    all_valid = bool(traj.turns) and all(
        t.valid for t in traj.turns if not t.error.startswith("execute")
    ) and not traj.error
    correct = traj.terminated and traj.terminal_action == ep.expect_terminal
    efficient = ep.min_swarms <= traj.swarms_run <= ep.max_swarms
    grounded = _grounded(traj)

    # Composite: termination is the gate (0.30), correct terminal action (0.30),
    # efficiency (0.20), all-valid turns (0.10), grounding when applicable (0.10).
    score = 0.0
    if traj.terminated:
        score += 0.30
    if correct:
        score += 0.30
    if efficient:
        score += 0.20
    if all_valid:
        score += 0.10
    if grounded is None:
        # no swarm to ground; redistribute to efficiency/validity already counted
        if efficient and all_valid:
            score += 0.10
    elif grounded:
        score += 0.10

    return TrajectoryScore(
        episode_id=ep.id, model=traj.model,
        terminated=traj.terminated, correct_action=correct,
        efficient=efficient, all_valid=all_valid, grounded=grounded,
        swarms_run=traj.swarms_run, turns=len(traj.turns),
        score=round(min(score, 1.0), 4),
        expect_terminal=ep.expect_terminal, got_terminal=traj.terminal_action,
        total_tokens_out=traj.total_tokens_out,
        total_latency_ms=traj.total_latency_ms,
        error=traj.error[:300],
    )
