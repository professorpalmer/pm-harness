from __future__ import annotations

"""Harness configuration. Driver is a swappable choice -- the research proved
the whole open-weights field drives at 100% under a good harness, so the default
is picked on efficiency (glm-5.2: 932 tok, clean MIT license)."""

from dataclasses import dataclass


@dataclass
class HarnessConfig:
    driver: str = "glm-5.2"          # default open-weights driver
    reach: str = "openrouter"        # one key, whole field
    budget: int = 3                  # orchestration steps per task
    state_dir: str = ""              # PM state dir; blank -> per-session temp
    worker_mode: str = "subprocess"

    @classmethod
    def from_env(cls) -> "HarnessConfig":
        import os
        return cls(
            driver=os.environ.get("HARNESS_DRIVER", "glm-5.2"),
            reach=os.environ.get("HARNESS_REACH", "openrouter"),
            budget=int(os.environ.get("HARNESS_BUDGET", "3")),
            state_dir=os.environ.get("HARNESS_STATE_DIR", ""),
        )
