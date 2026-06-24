from __future__ import annotations

"""Eval runner: for each driver model, run the whole battery, execute swarm
intents against Puppetmaster's local adapter, score deterministically, and
persist to the ledger.
"""

import time
import uuid
from typing import Optional

from .battery import BATTERY, TaskCase
from .bridge import execute_intent
from .intent import validate_intent, parse_intent_text, IntentError
from .scoring import score_attempt, Score
from .ledger import Ledger
from .drivers.base import Driver


def _maybe_execute(case: TaskCase, raw_text: str) -> Optional[bool]:
    if not (case.must_execute and case.expected_action == "run_swarm"):
        return None
    try:
        intent = validate_intent(parse_intent_text(raw_text))
    except IntentError:
        return False
    if intent.action != "run_swarm":
        return False
    try:
        res = execute_intent(intent)
    except Exception:
        return False
    return bool(res and res.num_artifacts > 0)


def run_driver(driver: Driver, ledger: Ledger, *, run_id: str, execute: bool = True) -> list:
    scores = []
    for case in BATTERY:
        resp = driver.complete(case.prompt)
        executed_ok = None
        if execute and not resp.error:
            executed_ok = _maybe_execute(case, resp.text)
        s = score_attempt(
            case, resp.text, model=driver.name, executed_ok=executed_ok,
            tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
            latency_ms=resp.latency_ms, driver_error=resp.error or "",
        )
        ledger.record(run_id, s)
        scores.append(s)
    return scores


def new_run_id() -> str:
    return f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
