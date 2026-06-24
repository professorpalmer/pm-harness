from __future__ import annotations

"""Stage 3: multi-turn driving. The single-turn battery saturated at 100% --
every competent model can emit one JSON object. The discriminating question is
whether a model can DRIVE A LOOP: act, read the result back, decide the next
step, and TERMINATE correctly without spinning or stopping prematurely.

An Episode is a scenario with a labeled expected trajectory shape. The runner
drives the model turn by turn, feeding Puppetmaster's real artifacts back into
the conversation, until a terminal action or a hard max-turn guard.
"""

from dataclasses import dataclass, field
from typing import Optional

from .intent import validate_intent, parse_intent_text, IntentError, DriverIntent
from .bridge import execute_intent, BridgeResult
from .drivers.base import Driver, SYSTEM_PROMPT


# Terminal actions end an episode; run_swarm continues it (there is a result to
# react to). A driver that never terminates is faulted by the max-turn guard.
TERMINAL_ACTIONS = ("answer", "stop")
MAX_TURNS = 6


MULTITURN_SYSTEM = SYSTEM_PROMPT + """

You are now driving a MULTI-TURN loop. After each run_swarm, you will be shown
the artifacts Puppetmaster produced. Use them to decide the next step:
  - If the objective is satisfied by the artifacts, emit action="stop" with a
    one-line rationale referencing what the artifacts established.
  - If genuinely more orchestration is needed, emit another run_swarm with a
    NARROWED goal (do not repeat the identical swarm).
  - Never loop the same swarm twice. Terminate when the work is done.
Emit ONLY the JSON object each turn."""


@dataclass
class Turn:
    index: int
    intent: Optional[DriverIntent]
    raw_text: str
    valid: bool
    error: str = ""
    executed: Optional[BridgeResult] = field(default=None, repr=False)
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0


@dataclass
class Trajectory:
    episode_id: str
    model: str
    turns: list
    terminated: bool          # reached a terminal action within MAX_TURNS
    terminal_action: Optional[str]
    swarms_run: int
    total_tokens_out: int
    total_latency_ms: float
    error: str = ""


def _feedback_text(result: BridgeResult) -> str:
    """Render executed artifacts back to the driver as the next user turn."""
    lines = [
        f"Puppetmaster ran your swarm (job {result.job_id}, mode={result.mode}).",
        f"It produced {result.num_artifacts} artifacts of types "
        f"{result.artifact_types}. Headlines:",
    ]
    for a in result.artifacts[:8]:
        lines.append(f"  - [{a['type']}] {a['headline']}")
    lines.append("\nDecide the next step (run_swarm with a narrowed goal, or stop).")
    return "\n".join(lines)


def run_episode(driver: Driver, episode, *, max_turns: int = MAX_TURNS) -> Trajectory:
    """Drive one episode to termination or the turn guard. Pure orchestration;
    scoring lives in scoring_multiturn."""
    turns: list = []
    swarms = 0
    tok_out = 0
    lat = 0.0
    err = ""
    terminal_action = None

    # The running conversation the driver sees. We keep it as a single rolling
    # user prompt (task + accumulated feedback) so any Driver implementation
    # works without needing multi-message memory.
    context = episode.prompt

    for i in range(max_turns):
        resp = driver.complete(context, system=MULTITURN_SYSTEM)
        tok_out += resp.tokens_out
        lat += resp.latency_ms
        if resp.error:
            turns.append(Turn(i, None, "", False, error=resp.error,
                              tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                              latency_ms=resp.latency_ms))
            err = resp.error
            break

        try:
            intent = validate_intent(parse_intent_text(resp.text))
            valid = True
            t_err = ""
        except IntentError as e:
            intent = None
            valid = False
            t_err = str(e)

        turn = Turn(i, intent, resp.text, valid, error=t_err,
                    tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                    latency_ms=resp.latency_ms)

        if not valid:
            turns.append(turn)
            break

        if intent.action in TERMINAL_ACTIONS:
            terminal_action = intent.action
            turns.append(turn)
            break

        # action == run_swarm: execute and feed artifacts back
        try:
            result = execute_intent(intent)
        except Exception as e:
            turn.error = f"execute: {e}"
            turns.append(turn)
            err = turn.error
            break
        turn.executed = result
        swarms += 1
        turns.append(turn)
        context = episode.prompt + "\n\n" + _feedback_text(result)
    else:
        # loop exhausted without terminal action
        terminal_action = None

    return Trajectory(
        episode_id=episode.id,
        model=driver.name,
        turns=turns,
        terminated=terminal_action is not None,
        terminal_action=terminal_action,
        swarms_run=swarms,
        total_tokens_out=tok_out,
        total_latency_ms=round(lat, 1),
        error=err,
    )
