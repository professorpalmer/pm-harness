from __future__ import annotations

"""Stage 4: ranking episodes. The V2 battery saturated (every competent model
100%) because each scenario had one obvious move. Stage 4 introduces episodes
where the CORRECT trajectory requires real judgment, so strong drivers separate:

  1. Sequenced multi-swarm: the right path is investigate -> narrow to a
     DIFFERENT sub-question -> conclude (min_swarms 2). A driver that concludes
     after one swarm is premature; one that repeats the same swarm is wasteful.
  2. Stop-early traps (paired): identical surface, opposite correct action.
     - inconclusive-first: the first swarm's findings explicitly say MORE work is
       needed -> a good driver continues; a lazy one stops prematurely.
     - conclusive-first: the first swarm's findings explicitly resolve it -> a
       good driver stops; an over-eager one keeps burning budget.
     The driver must READ the findings to decide -- not follow a fixed pattern.

Findings substrates are turn-indexed: the runner feeds substrate[swarms_run] so
the signal evolves across turns (turn 1 inconclusive -> turn 2 conclusive).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class EpisodeS4:
    id: str
    scenario: str
    prompt: str
    expect_terminal: str
    min_swarms: int
    max_swarms: int
    budget: int
    # findings fed per swarm index (0 = after first swarm, 1 = after second, ...)
    substrates: tuple = field(default_factory=tuple)
    notes: str = ""
    variant: str = "s4"


# Sequenced: first pass maps the surface but flags an unexamined subsystem;
# the right move is a SECOND, narrowed swarm, then conclude.
_SEQ_S0 = (
    "FINDINGS (pass 1): mapped the request pipeline end to end. One subsystem -- "
    "the async job queue -- was referenced but NOT examined; its failure modes are "
    "unknown. MORE INVESTIGATION NEEDED: the queue is the remaining unknown."
)
_SEQ_S1 = (
    "FINDINGS (pass 2, queue): the async queue retries without idempotency; a "
    "duplicate-delivery bug is confirmed at queue/consumer.py:also no further "
    "unknowns. CONCLUSION REACHED: the full pipeline is now understood."
)

# Inconclusive-first trap: first findings explicitly say more work needed.
_INC_S0 = (
    "FINDINGS (pass 1): partial. The symptom is reproduced but the ROOT CAUSE is "
    "NOT yet identified -- two candidate modules remain unexamined. This is "
    "INCONCLUSIVE; do not stop, narrow to the candidates."
)
_INC_S1 = (
    "FINDINGS (pass 2): root cause IDENTIFIED -- a stale cache key in auth/cache.py "
    "returns expired sessions. Evidence attached. CONCLUSION REACHED."
)

# Conclusive-first trap: first findings already resolve it.
_CON_S0 = (
    "FINDINGS (pass 1): the single biggest risk is IDENTIFIED with evidence -- "
    "unbounded recursion in report/build.py:also stack-overflow on deep trees. "
    "No open questions. CONCLUSION REACHED; the objective is satisfied."
)


EPISODES_S4 = [
    EpisodeS4("seq_two_pass", "sequenced",
        "Investigate this service's request pipeline fully and report the "
        "complete picture once you actually understand every subsystem.",
        "stop", min_swarms=2, max_swarms=3, budget=4,
        substrates=(_SEQ_S0, _SEQ_S1)),
    EpisodeS4("trap_inconclusive", "stop_early_trap",
        "Find the root cause of the reported session-expiry bug, then report it.",
        "stop", min_swarms=2, max_swarms=3, budget=4,
        substrates=(_INC_S0, _INC_S1),
        notes="must NOT stop after pass 1 (inconclusive)"),
    EpisodeS4("trap_conclusive", "stop_early_trap",
        "Identify the single biggest correctness risk in this module and report it.",
        "stop", min_swarms=1, max_swarms=1, budget=4,
        substrates=(_CON_S0,),
        notes="must stop after pass 1 (already conclusive); continuing wastes budget"),
]
