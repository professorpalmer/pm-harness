from __future__ import annotations

"""Stage 3.5 episodes: richer, budget-aware, with prompt variants.

Three fixes over Stage 3, each targeting a named confound:
  1. findings_substrate -- a curated, CONCLUSIVE findings digest attached to the
     turn feedback. Real Puppetmaster still executes (proves the seam), but the
     SIGNAL the driver reasons about is substantive, not the demo adapter's thin
     stubs. This is gold-fixture eval scaffolding (clearly labeled), so a careful
     model no longer has a legitimate reason to keep digging -- "keep going" now
     reflects judgment, not a starved signal.
  2. budget -- each episode declares an orchestration budget; the runner injects
     it into the system prompt. Tests whether a model RESPECTS a budget (the real
     harness constraint), separating economy from loop-burn.
  3. variant -- "vague" vs "explicit" phrasing of the same scenario. A strong
     driver terminates correctly on BOTH; a model that only works with an
     explicit cue is a weaker autonomous driver. Scoring rewards consistency.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class EpisodeV2:
    id: str
    scenario: str                 # scenario family (for pairing variants)
    variant: str                  # "vague" | "explicit"
    prompt: str
    expect_terminal: str          # "stop" | "answer"
    min_swarms: int
    max_swarms: int
    budget: int                   # orchestration steps the driver is told it has
    findings_substrate: Optional[str] = None  # conclusive digest fed after swarm
    notes: str = ""


# A substantive, conclusive findings digest. Represents what a real multi-role
# swarm returns on the scenario. Labeled scaffolding; not real PM output.
_AUTH_FINDINGS = (
    "FINDINGS DIGEST (substantive):\n"
    "- auth flow fully mapped: login -> JWT issued (RS256) -> middleware verifies "
    "on every request -> refresh via /auth/refresh. 4 entry points, all traced.\n"
    "- session store: Redis, 24h TTL, keyed by sub claim. No gaps found.\n"
    "- CONCLUSION REACHED: the authentication mechanism is fully understood; no "
    "open questions remain. Nothing further to investigate."
)
_RISK_FINDINGS = (
    "FINDINGS DIGEST (substantive):\n"
    "- single biggest correctness risk IDENTIFIED: unbounded retry in the payment "
    "webhook handler can double-charge on provider 5xx (no idempotency key).\n"
    "- evidence: handler at payments/webhook.py:88, no dedupe; sibling paths OK.\n"
    "- CONCLUSION REACHED: the top risk is established with evidence. The audit "
    "objective is satisfied; no further orchestration needed."
)

EPISODES_V2 = [
    # --- scenario: investigate-then-conclude (budget 3) ---
    EpisodeV2("invest_vague", "investigate", "vague",
        "Investigate how authentication works across this codebase.",
        "stop", 1, 2, budget=3, findings_substrate=_AUTH_FINDINGS),
    EpisodeV2("invest_explicit", "investigate", "explicit",
        "Investigate how authentication works across this codebase. Run ONE "
        "investigation pass, then once the findings explain the flow, STOP and "
        "report your conclusion. Do not re-investigate.",
        "stop", 1, 2, budget=3, findings_substrate=_AUTH_FINDINGS),
    # --- scenario: audit-then-conclude (budget 3) ---
    EpisodeV2("audit_vague", "audit", "vague",
        "Audit this repository for the single biggest correctness risk.",
        "stop", 1, 2, budget=3, findings_substrate=_RISK_FINDINGS),
    EpisodeV2("audit_explicit", "audit", "explicit",
        "Audit this repository for the single biggest correctness risk. Once the "
        "audit identifies it with evidence, STOP and report. One pass is enough.",
        "stop", 1, 2, budget=3, findings_substrate=_RISK_FINDINGS),
    # --- scenario: trivial (budget 1, zero swarms) ---
    EpisodeV2("trivial_vague", "trivial", "vague",
        "What does the acronym JSON stand for?",
        "answer", 0, 0, budget=1),
    EpisodeV2("trivial_explicit", "trivial", "explicit",
        "Answer directly, with no orchestration: what does the acronym JSON "
        "stand for?",
        "answer", 0, 0, budget=1),
    # --- scenario: already-done (budget 1, zero swarms) ---
    EpisodeV2("done_vague", "already_done", "vague",
        "The refactor is already merged and CI is green.",
        "stop", 0, 0, budget=1),
    EpisodeV2("done_explicit", "already_done", "explicit",
        "The refactor is already merged and CI is green, so there is nothing to "
        "do. Acknowledge and stop without orchestrating.",
        "stop", 0, 0, budget=1),
]
