from __future__ import annotations

"""Deterministic scoring for a single driver attempt on a single task.

Metrics (all objective, no LLM-as-judge):
  json_valid:      driver output parsed into a JSON object at all
  schema_valid:    parsed object passed validate_intent (a real DriverIntent)
  action_correct:  intent.action matched the task's ground-truth label
  executed_ok:     for must_execute swarm cases, PM returned >=1 artifact
  score:           composite 0..1 (see weights) -- the headline number
"""

from dataclasses import dataclass, asdict
from typing import Optional

from .intent import validate_intent, parse_intent_text, IntentError, DriverIntent
from .battery import TaskCase


@dataclass
class Score:
    task_id: str
    model: str
    json_valid: bool
    schema_valid: bool
    action_correct: bool
    executed_ok: Optional[bool]   # None when execution not applicable
    score: float
    expected_action: str
    got_action: Optional[str]
    error: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0

    def to_row(self) -> dict:
        return asdict(self)


def score_attempt(
    case: TaskCase,
    raw_text: str,
    *,
    model: str,
    executed_ok: Optional[bool] = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0.0,
    driver_error: str = "",
) -> Score:
    json_valid = False
    schema_valid = False
    action_correct = False
    got_action = None
    err = driver_error

    intent: Optional[DriverIntent] = None
    if not driver_error:
        try:
            obj = parse_intent_text(raw_text)
            json_valid = True
        except IntentError as e:
            err = f"parse: {e}"
            obj = None
        if json_valid:
            try:
                intent = validate_intent(obj)
                schema_valid = True
                got_action = intent.action
                action_correct = (intent.action == case.expected_action)
            except IntentError as e:
                err = f"schema: {e}"

    # Composite score. Weights chosen so that: emitting valid schema is the
    # floor capability (0.4), making the right decision is the bulk (0.4), and
    # actually getting PM to produce artifacts when required closes it (0.2).
    score = 0.0
    if json_valid:
        score += 0.15
    if schema_valid:
        score += 0.25
    if action_correct:
        score += 0.40
    if case.must_execute and case.expected_action == "run_swarm":
        if executed_ok:
            score += 0.20
    else:
        # No execution gate for this case; redistribute that weight to decision
        # so non-swarm cases still top out at 1.0 when decided correctly.
        if action_correct:
            score += 0.20

    return Score(
        task_id=case.id,
        model=model,
        json_valid=json_valid,
        schema_valid=schema_valid,
        action_correct=action_correct,
        executed_ok=executed_ok,
        score=round(min(score, 1.0), 4),
        expected_action=case.expected_action,
        got_action=got_action,
        error=err[:300],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=round(latency_ms, 1),
    )
