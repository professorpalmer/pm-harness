from __future__ import annotations

"""Multi-turn episodes with labeled expected trajectory shapes. These probe the
discriminating behaviors single-turn cannot: correct termination, efficiency (no
redundant swarms), and not stopping prematurely.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Episode:
    id: str
    prompt: str
    expect_terminal: str          # "stop" | "answer"
    min_swarms: int               # least swarms a correct driver must run
    max_swarms: int               # most before it is wastefully looping
    notes: str = ""


EPISODES = [
    # Investigate once, read the result, conclude. The canonical good loop.
    Episode("invest_then_stop",
            "Investigate how authentication works across this codebase and, once "
            "you understand it, conclude. Do not over-orchestrate.",
            expect_terminal="stop", min_swarms=1, max_swarms=2),
    # Trivial: should answer immediately, ZERO swarms.
    Episode("trivial_answer",
            "What does the acronym JSON stand for? One line.",
            expect_terminal="answer", min_swarms=0, max_swarms=0),
    # Already-done: should stop immediately, ZERO swarms.
    Episode("already_done",
            "The refactor is already merged and CI is green. There is nothing "
            "left to do here.",
            expect_terminal="stop", min_swarms=0, max_swarms=0),
    # A genuine investigation that warrants exactly one swarm then a conclusion;
    # a weak driver will either loop or stop before running anything.
    Episode("audit_then_conclude",
            "Audit this repository for the single biggest correctness risk, then "
            "report your conclusion and stop.",
            expect_terminal="stop", min_swarms=1, max_swarms=2),
]
