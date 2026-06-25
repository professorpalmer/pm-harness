from __future__ import annotations

"""Stage 4 reference drivers: a findings-READER (smart) and a LAZY stopper. They
prove the Stage 4 battery actually discriminates -- the reader should pass, the
lazy one should fail the inconclusive trap and sequenced episodes."""

import json, time
from pmharness.drivers.base import DriverResponse, SYSTEM_PROMPT


class ReaderStub:
    """Reads the findings: continues while 'inconclusive/more needed', stops on
    'conclusion reached'. The behavior a good driver should exhibit."""
    name = "stub-reader"
    def complete(self, prompt, *, system=SYSTEM_PROMPT):
        t0=time.time(); p=prompt.lower()
        if "conclusion reached" in p:
            intent={"action":"stop","rationale":"findings conclude the objective; evidence established"}
        elif ("inconclusive" in p or "more investigation needed" in p
              or "do not stop" in p or "remaining unknown" in p):
            intent={"action":"run_swarm","goal":"narrow to the open question flagged by findings","rationale":"findings inconclusive; continue"}
        elif "puppetmaster ran your swarm" in p:
            # findings present but neither cue -> default conclude
            intent={"action":"stop","rationale":"findings sufficient"}
        else:
            intent={"action":"run_swarm","goal":prompt.strip()[:160],"rationale":"first investigation pass"}
        text=json.dumps(intent)
        return DriverResponse(text=text, tokens_in=len(prompt.split()), tokens_out=len(text.split()),
                              latency_ms=(time.time()-t0)*1000, model=self.name)


class LazyStub:
    """Always stops after the first swarm regardless of findings -- the premature
    failure mode the inconclusive trap must catch."""
    name = "stub-lazy"
    def complete(self, prompt, *, system=SYSTEM_PROMPT):
        t0=time.time(); p=prompt.lower()
        if "puppetmaster ran your swarm" in p:
            intent={"action":"stop","rationale":"good enough"}
        else:
            intent={"action":"run_swarm","goal":prompt.strip()[:160],"rationale":"one pass"}
        text=json.dumps(intent)
        return DriverResponse(text=text, tokens_in=len(prompt.split()), tokens_out=len(text.split()),
                              latency_ms=(time.time()-t0)*1000, model=self.name)
