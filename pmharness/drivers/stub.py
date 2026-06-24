from __future__ import annotations

"""StubDriver: a deterministic, offline driver that emits correct DriverIntents
by simple keyword policy. It exists to prove the rig end-to-end with zero API
keys, and to serve as the perfect-score control row in results (a real model is
judged relative to this ceiling).
"""

import json
import time

from .base import DriverResponse, SYSTEM_PROMPT


class StubDriver:
    name = "stub-oracle"

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        t0 = time.time()
        p = task_prompt.lower()

        trivial = any(
            k in p for k in ("what is", "define", "definition of", "abbreviation")
        ) and "codebase" not in p and "repo" not in p

        already_done = "already complete" in p or "nothing left" in p or "no action" in p

        if already_done:
            intent = {"action": "stop", "rationale": "work already complete"}
        elif trivial:
            intent = {"action": "answer", "rationale": "trivial; no orchestration needed"}
        else:
            roles = None
            if "test" in p or "coverage" in p:
                roles = ["test-coverage-reviewer", "explore"]
            elif "conflict" in p or "audit" in p:
                roles = ["conflict-auditor", "explore"]
            intent = {
                "action": "run_swarm",
                "goal": task_prompt.strip()[:300],
                "rationale": "requires multi-file investigation",
            }
            if roles:
                intent["roles"] = roles

        text = json.dumps(intent)
        return DriverResponse(
            text=text,
            tokens_in=len(task_prompt.split()),
            tokens_out=len(text.split()),
            latency_ms=(time.time() - t0) * 1000.0,
            model=self.name,
        )
