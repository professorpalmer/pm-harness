from __future__ import annotations

"""Budget-aware multi-turn oracle for Stage 3.5. Concludes immediately once a
findings digest is present (respects budget); answers trivia; stops already-done.
Establishes the 100% ceiling under the sharper scorer."""

import json, time
from .base import DriverResponse, SYSTEM_PROMPT


class StubV2Driver:
    name = "stub-oracle-v2"

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        t0=time.time(); p=task_prompt.lower()
        saw = "puppetmaster ran your swarm" in p or "findings digest" in p
        if saw:
            intent={"action":"stop","rationale":"the findings digest established the conclusion; objective resolved"}
        elif "acronym" in p or "stand for" in p:
            intent={"action":"answer","rationale":"trivial, no orchestration"}
        elif "already merged" in p or ("nothing to do" in p) or ("ci is green" in p):
            intent={"action":"stop","rationale":"work already complete"}
        else:
            intent={"action":"run_swarm","goal":task_prompt.strip()[:200],"rationale":"one investigation pass within budget"}
        text=json.dumps(intent)
        return DriverResponse(text=text, tokens_in=len(task_prompt.split()),
                              tokens_out=len(text.split()), latency_ms=(time.time()-t0)*1000.0, model=self.name)
