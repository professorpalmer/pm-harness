from __future__ import annotations

"""AutoBudget: the safety governor for Fully-Auto (unattended) mode.

Unattended autonomy = "allow all" with no human in the loop. That is exactly
where runaway token spend and confused loops happen (we watched qwen grind 7
swarms on bad substrate while supervised). So the governor is built and tested
BEFORE the autonomy it guards -- the brakes go in before the engine.

Three hard ceilings + a killswitch + a tripwire:
  - max_tokens     : cumulative driver tokens_out across the run
  - max_seconds    : wall-clock since the run started
  - max_swarms     : total swarms dispatched
  - killswitch     : a stop-file path; if it exists, halt immediately (the user
                     can `touch` it from anywhere to stop an overnight run)
  - max_idle_steps : consecutive pilot steps with no NEW findings -> stall halt
                     (stops a confused loop burning budget on nothing)

check() returns None to proceed or a string reason to HALT. The governor never
trusts the model to stop itself; it is enforced by the loop around the model.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AutoBudget:
    max_tokens: int = 100_000
    max_seconds: int = 3600          # 1 hour default
    max_swarms: int = 40
    max_idle_steps: int = 3          # consecutive no-new-finding steps before halt
    killswitch_path: str = ""        # touch this file to stop a run

    # live counters (mutated by the loop)
    tokens_used: int = field(default=0)
    swarms_used: int = field(default=0)
    idle_steps: int = field(default=0)
    started_at: float = field(default_factory=time.time)
    _halted_reason: Optional[str] = field(default=None)

    def start(self) -> "AutoBudget":
        self.started_at = time.time()
        self.tokens_used = 0
        self.swarms_used = 0
        self.idle_steps = 0
        self._halted_reason = None
        return self

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def add_tokens(self, n: int) -> None:
        self.tokens_used += max(0, int(n or 0))

    def add_swarm(self) -> None:
        self.swarms_used += 1

    def note_findings(self, new_count: int) -> None:
        """Track stall: a step that produced no new findings increments idle."""
        if new_count > 0:
            self.idle_steps = 0
        else:
            self.idle_steps += 1

    def killed(self) -> bool:
        return bool(self.killswitch_path) and os.path.exists(self.killswitch_path)

    def check(self) -> Optional[str]:
        """Return a HALT reason, or None to proceed. Checked every loop step."""
        if self._halted_reason:
            return self._halted_reason
        if self.killed():
            return self._halt(f"killswitch tripped ({self.killswitch_path})")
        if self.tokens_used >= self.max_tokens:
            return self._halt(f"token ceiling reached ({self.tokens_used}/{self.max_tokens})")
        if self.elapsed >= self.max_seconds:
            return self._halt(f"time ceiling reached ({int(self.elapsed)}s/{self.max_seconds}s)")
        if self.swarms_used >= self.max_swarms:
            return self._halt(f"swarm ceiling reached ({self.swarms_used}/{self.max_swarms})")
        if self.idle_steps >= self.max_idle_steps:
            return self._halt(f"stall: {self.idle_steps} steps with no new findings")
        return None

    def _halt(self, reason: str) -> str:
        self._halted_reason = reason
        return reason

    def snapshot(self) -> dict:
        return {
            "tokens_used": self.tokens_used, "max_tokens": self.max_tokens,
            "swarms_used": self.swarms_used, "max_swarms": self.max_swarms,
            "elapsed_s": int(self.elapsed), "max_seconds": self.max_seconds,
            "idle_steps": self.idle_steps, "max_idle_steps": self.max_idle_steps,
            "halted": self._halted_reason,
        }

    @classmethod
    def from_env(cls) -> "AutoBudget":
        def _i(name, default):
            try:
                return int(os.environ.get(name, "").strip() or default)
            except ValueError:
                return default
        return cls(
            max_tokens=_i("HARNESS_AUTO_MAX_TOKENS", 100_000),
            max_seconds=_i("HARNESS_AUTO_MAX_SECONDS", 3600),
            max_swarms=_i("HARNESS_AUTO_MAX_SWARMS", 40),
            max_idle_steps=_i("HARNESS_AUTO_MAX_IDLE", 3),
            killswitch_path=os.environ.get("HARNESS_AUTO_KILLSWITCH", "").strip(),
        )
