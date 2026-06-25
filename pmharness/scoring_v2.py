from __future__ import annotations

"""Stage 3.5 scoring: sharper, with budget-overrun and premature-stop penalties.

A correct trajectory: terminates with the right action, runs a swarm count
within [min,max], stays within budget, grounds its conclusion, and is valid on
every turn. The new penalties make the score reflect JUDGMENT, not the
starved-signal artifact of Stage 3.
"""

from dataclasses import dataclass, asdict
from typing import Optional

from .episode_v2 import EpisodeV2
from .episode_v2_runner import TrajectoryV2


@dataclass
class ScoreV2:
    episode_id: str
    scenario: str
    variant: str
    model: str
    terminated: bool
    correct_action: bool
    within_budget: bool
    efficient: bool
    premature: bool          # stopped/answered with too FEW swarms
    grounded: Optional[bool]
    all_valid: bool
    swarms_run: int
    budget: int
    turns: int
    score: float
    expect_terminal: str
    got_terminal: Optional[str]
    total_tokens_out: int
    total_latency_ms: float
    error: str = ""

    def to_row(self) -> dict:
        return asdict(self)


def _grounded(ep: EpisodeV2, traj: TrajectoryV2) -> Optional[bool]:
    if traj.swarms_run < 1:
        return None
    rationale = ""
    for t in traj.turns:
        if t.intent and t.intent.action in ("stop", "answer"):
            rationale = (t.intent.rationale or "").lower()
    if not rationale:
        return False
    return any(w in rationale for w in
               ("finding", "established", "conclu", "identified", "evidence",
                "risk", "auth", "understood", "mapped", "resolved", "swarm"))


def score_v2(ep: EpisodeV2, traj: TrajectoryV2) -> ScoreV2:
    correct = traj.terminated and traj.terminal_action == ep.expect_terminal
    within_budget = traj.swarms_run <= ep.budget
    efficient = ep.min_swarms <= traj.swarms_run <= ep.max_swarms
    premature = traj.swarms_run < ep.min_swarms
    grounded = _grounded(ep, traj)
    all_valid = bool(traj.turns) and all(
        t.valid for t in traj.turns if not t.error.startswith("execute")
    ) and not traj.error

    # Weights: termination is the gate (0.25), correct action (0.25), efficiency
    # within range (0.20), staying within budget (0.15), grounding (0.10),
    # validity (0.05). Premature stop and budget overrun zero out the relevant
    # credit, so neither "give up early" nor "loop forever" scores well.
    score = 0.0
    if traj.terminated:
        score += 0.25
    if correct:
        score += 0.25
    if efficient and not premature:
        score += 0.20
    if within_budget:
        score += 0.15
    if grounded is None:
        if efficient:
            score += 0.10
    elif grounded:
        score += 0.10
    if all_valid:
        score += 0.05

    return ScoreV2(
        episode_id=ep.id, scenario=ep.scenario, variant=ep.variant, model=traj.model,
        terminated=traj.terminated, correct_action=correct,
        within_budget=within_budget, efficient=efficient, premature=premature,
        grounded=grounded, all_valid=all_valid, swarms_run=traj.swarms_run,
        budget=ep.budget, turns=len(traj.turns), score=round(min(score, 1.0), 4),
        expect_terminal=ep.expect_terminal, got_terminal=traj.terminal_action,
        total_tokens_out=traj.total_tokens_out, total_latency_ms=traj.total_latency_ms,
        error=traj.error[:300],
    )
