from __future__ import annotations

"""StubMultiTurnDriver: deterministic oracle for the multi-turn battery. It
reads the rolling context: if Puppetmaster feedback is present, it concludes
(stop, grounded); otherwise it makes the right first move (answer trivia, stop
already-done, else swarm once). Establishes the 100% trajectory ceiling.
"""

import json
import time

from .base import DriverResponse, SYSTEM_PROMPT


class StubMultiTurnDriver:
    name = "stub-oracle-mt"

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        t0 = time.time()
        p = task_prompt.lower()
        saw_feedback = "puppetmaster ran your swarm" in p

        if saw_feedback:
            intent = {"action": "stop",
                      "rationale": "the swarm artifacts and findings establish the answer"}
        elif ("stand for" in p or "acronym" in p or "one line" in p) and "codebase" not in p:
            intent = {"action": "answer", "rationale": "trivial, no orchestration needed"}
        elif "already" in p and ("merged" in p or "nothing left" in p or "green" in p):
            intent = {"action": "stop", "rationale": "work already complete"}
        else:
            intent = {"action": "run_swarm",
                      "goal": task_prompt.strip()[:200],
                      "rationale": "needs one investigation pass"}

        text = json.dumps(intent)
        return DriverResponse(text=text, tokens_in=len(task_prompt.split()),
                              tokens_out=len(text.split()),
                              latency_ms=(time.time()-t0)*1000.0, model=self.name)
