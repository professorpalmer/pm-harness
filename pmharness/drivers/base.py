from __future__ import annotations

"""Driver protocol: anything that, given a task prompt, returns raw text the
harness will parse into a DriverIntent. Keeps the model boundary clean -- the
driver returns text + token accounting; parsing/validation/scoring is the
harness's job, identically for every model.
"""

from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class DriverResponse:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    model: str = ""
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)


SYSTEM_PROMPT = """You are the driver loop for Puppetmaster, an orchestration engine.
You do NOT write prose explanations or narrate your actions. For each task you
emit exactly ONE JSON object -- a DriverIntent -- and nothing else.

Schema:
  action:      one of "run_swarm" | "answer" | "stop"   (required)
  goal:        string; REQUIRED when action=run_swarm; the swarm objective
  roles:       optional array; subset of
               ["explore","pipeline-mapper","decision-explainer",
                "conflict-auditor","test-coverage-reviewer"]
  worker_mode: optional; "subprocess" | "inline" | "daemon"  (default subprocess)
  rationale:   one short sentence on why this action

Decision policy:
  - Use action="run_swarm" for tasks that require investigating, auditing,
    refactoring, or analyzing a codebase across multiple files.
  - Use action="answer" for trivial questions you can answer directly with no
    orchestration (definitions, one-line facts). Do not waste a swarm on these.
  - Use action="stop" when the work is already complete or no action is needed.

Output ONLY the JSON object."""


class Driver(Protocol):
    name: str

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        ...

    def chat(self, messages: list, *, tools: Optional[list] = None, system: Optional[str] = None) -> DriverResponse:
        ...

