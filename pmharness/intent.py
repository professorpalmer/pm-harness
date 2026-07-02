from __future__ import annotations

"""DriverIntent: the structured object an LLM driver must emit to drive
Puppetmaster. This is the contract the whole thesis rests on. A driver that
cannot reliably emit a valid DriverIntent cannot run the harness, full stop.

Kept deliberately small and unambiguous: three actions, a handful of fields.
The model is judged on whether it can hit this target, not on prose.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# The three things a driver can decide to do at any step. "answer" is
# load-bearing for the token thesis: a good driver does NOT swarm trivia.
VALID_ACTIONS = ("run_swarm", "answer", "stop")

# Worker modes Puppetmaster's Orchestrator.run accepts.
VALID_WORKER_MODES = ("subprocess", "inline", "daemon")

# Roles the harness recognizes for a swarm. Mirrors the cursor-swarm default
# set plus the generic explore role. A driver may pass a subset; unknown roles
# are a validation failure (caught, scored, not silently dropped).
KNOWN_ROLES = (
    "explore",
    "pipeline-mapper",
    "decision-explainer",
    "conflict-auditor",
    "test-coverage-reviewer",
)

# Each role investigates a distinct facet, so a multi-role swarm fans out into
# genuinely different work instead of N identical passes. The lens is appended
# to the shared goal to point the worker at its angle. Kept as plain data here
# (PM-free, pure) so both the harness and its tests can reason about roles
# without importing the executor.
ROLE_LENSES: dict[str, str] = {
    "explore": (
        "Lens: STRUCTURAL TOUR. Map the packages/modules, entry points, and how "
        "the pieces fit together. Surface the high-level architecture and the "
        "load-bearing components."
    ),
    "pipeline-mapper": (
        "Lens: DATA/CONTROL FLOW. Trace how a request or task moves through the "
        "system end to end, stage by stage. Identify the seams, hand-offs, and "
        "bottlenecks between components."
    ),
    "decision-explainer": (
        "Lens: DESIGN DECISIONS. Explain the key architectural choices and their "
        "trade-offs -- why the code is shaped this way, which abstractions are "
        "load-bearing, and the constraints behind them."
    ),
    "conflict-auditor": (
        "Lens: CONFLICTS & INCONSISTENCIES. Hunt for contradictory assumptions, "
        "duplicated or dead code, inconsistent patterns, and correctness/robustness "
        "risks across modules. Flag each with evidence."
    ),
    "test-coverage-reviewer": (
        "Lens: TEST COVERAGE & QUALITY. Assess what is tested vs dangerously "
        "untested, brittle or low-value tests, and the highest-leverage tests to "
        "add for confidence at scale."
    ),
}

# Signals in a goal that mean the user wants a broad, multi-angle investigation
# (an audit) rather than one narrow question. Deterministic substring match --
# no model, no PM -- so role inference is a pure function of the goal text.
_BROAD_AUDIT_SIGNALS = (
    "audit", "review", "assess", "evaluat", "quality", "robust", "scale",
    "scalab", "improve", "better", "health", "tech debt", "weakness",
    "vulnerab", "overall", "comprehensive", "entire", "whole", "deep dive",
    "harden", "best practice",
)
_FLOW_SIGNALS = ("pipeline", "data flow", "control flow", "end to end", "end-to-end", "trace")

# The full audit fan-out, ordered by descending payoff for a broad platform pass.
_FULL_AUDIT_ROLES = [
    "explore",
    "conflict-auditor",
    "test-coverage-reviewer",
    "pipeline-mapper",
    "decision-explainer",
]


def infer_roles(goal: str) -> list:
    """Pick a role set from the goal when the driver supplied none.

    Broad/audit-flavored goals fan out across every analysis lens so the swarm
    hits the platform from multiple angles at once; a flow-shaped goal adds the
    pipeline lens; anything else stays a single general explorer. Pure and
    deterministic -- a function of the goal text only.
    """
    text = (goal or "").lower()
    if any(signal in text for signal in _BROAD_AUDIT_SIGNALS):
        return list(_FULL_AUDIT_ROLES)
    if any(signal in text for signal in _FLOW_SIGNALS):
        return ["explore", "pipeline-mapper"]
    return ["explore"]


class IntentError(ValueError):
    """Raised when a payload cannot be coerced into a valid DriverIntent."""


@dataclass(frozen=True)
class DriverIntent:
    action: str
    goal: Optional[str] = None
    roles: Optional[list] = None
    worker_mode: str = "subprocess"
    rationale: str = ""
    # Free-form, model-supplied; never trusted for control flow, kept for audit.
    raw: Optional[dict] = field(default=None, compare=False, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


def _coerce_roles(value: Any) -> Optional[list]:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise IntentError("roles must be a list of strings")
    roles = [str(r).strip() for r in value if str(r).strip()]
    return roles or None


def validate_intent(payload: Any) -> DriverIntent:
    """Coerce an arbitrary parsed object into a DriverIntent or raise
    IntentError with a precise reason. Pure and deterministic so it can be
    unit-tested and so scoring is reproducible.
    """
    if isinstance(payload, str):
        payload = parse_intent_text(payload)
    if not isinstance(payload, dict):
        raise IntentError(f"intent must be a JSON object, got {type(payload).__name__}")

    action = payload.get("action")
    if action not in VALID_ACTIONS:
        raise IntentError(f"action must be one of {VALID_ACTIONS}, got {action!r}")

    worker_mode = payload.get("worker_mode", "subprocess") or "subprocess"
    if worker_mode not in VALID_WORKER_MODES:
        raise IntentError(
            f"worker_mode must be one of {VALID_WORKER_MODES}, got {worker_mode!r}"
        )

    roles = _coerce_roles(payload.get("roles"))
    if roles is not None:
        unknown = [r for r in roles if r not in KNOWN_ROLES]
        if unknown:
            raise IntentError(f"unknown roles: {unknown}; known={list(KNOWN_ROLES)}")

    goal = payload.get("goal")
    if goal is not None:
        goal = str(goal).strip() or None

    if action == "run_swarm" and not goal:
        raise IntentError("action=run_swarm requires a non-empty goal")

    rationale = str(payload.get("rationale", "") or "").strip()

    return DriverIntent(
        action=action,
        goal=goal,
        roles=roles,
        worker_mode=worker_mode,
        rationale=rationale,
        raw=payload if isinstance(payload, dict) else None,
    )


def parse_intent_text(text: str) -> dict:
    """Extract the first JSON object from a model's raw text output.

    Real open-weights models wrap JSON in prose or ```json fences. We are
    lenient about the wrapper (that is the harness's job, not the model's) but
    strict about the content (validate_intent stays rigorous). The split keeps
    the 'valid JSON' and 'valid schema' metrics honestly separate.
    """
    if not isinstance(text, str):
        raise IntentError("driver output was not text")
    s = text.strip()

    # Strip a fenced code block if present.
    if "```" in s:
        parts = s.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                s = p
                break

    # Find the first balanced top-level JSON object.
    start = s.find("{")
    if start == -1:
        raise IntentError("no JSON object found in driver output")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise IntentError(f"invalid JSON: {e}") from e
    raise IntentError("unbalanced JSON object in driver output")


INTENT_JSON_SCHEMA_HINT = {
    "action": "one of run_swarm | answer | stop",
    "goal": "string; REQUIRED when action=run_swarm; the swarm objective",
    "roles": f"optional list; subset of {list(KNOWN_ROLES)}",
    "worker_mode": "optional; one of subprocess | inline | daemon (default subprocess)",
    "rationale": "one sentence on why this action",
}
