from __future__ import annotations

"""The task battery: prompts with ground-truth labels for what a correct driver
should DECIDE. Each case carries the expected action (and, for swarms, whether a
swarm must actually produce artifacts). Labels make scoring deterministic and
let us measure decision accuracy, not just JSON validity.

Three buckets, deliberately balanced:
  - swarm:   genuinely needs orchestration (multi-file investigation/audit)
  - answer:  trivial, must NOT waste a swarm (the token thesis in miniature)
  - stop:    already done / no action needed
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskCase:
    id: str
    prompt: str
    expected_action: str            # run_swarm | answer | stop
    must_execute: bool = False      # if run_swarm, require artifacts back
    notes: str = ""


BATTERY = [
    # --- run_swarm cases ---
    TaskCase("swarm_audit", "Audit this codebase for security risks across all "
             "modules and summarize what could break.", "run_swarm", True),
    TaskCase("swarm_refactor", "Trace every call path that touches the payment "
             "module in this repo and propose a refactor.", "run_swarm", True),
    TaskCase("swarm_tests", "Review test coverage for the repo and find the "
             "biggest untested risk areas.", "run_swarm", True,
             notes="should consider test-coverage-reviewer role"),
    TaskCase("swarm_conflict", "Audit the codebase for conflicting assumptions "
             "between the auth layer and the session store.", "run_swarm", True,
             notes="should consider conflict-auditor role"),
    TaskCase("swarm_explore", "Investigate how data flows from the ingestion "
             "pipeline through to the database in this codebase.", "run_swarm", True),
    # --- answer cases (must NOT swarm) ---
    TaskCase("ans_define", "What is the definition of idempotency?", "answer"),
    TaskCase("ans_abbrev", "What is the abbreviation MCP short for in one line?", "answer"),
    TaskCase("ans_fact", "Define what a SQLite WAL file is, briefly.", "answer"),
    # --- stop cases ---
    TaskCase("stop_done", "The migration is already complete and verified; "
             "there is nothing left to do.", "stop"),
    TaskCase("stop_noop", "No action is needed here; just acknowledging.", "stop"),
]
