from __future__ import annotations

"""Driver registry: the models under study. Open-weights harness candidates
(Kimi, GLM) plus a frontier control row. Keys live only in the environment.
Factories are lazy so importing this module never requires a key.
"""

from typing import Callable, Dict

from .drivers.base import Driver
from .drivers.stub import StubDriver
from .drivers.openai_compat import OpenAICompatDriver


REGISTRY: Dict[str, Callable[[], Driver]] = {
    "stub-oracle": lambda: StubDriver(),
    "kimi-k2": lambda: OpenAICompatDriver(
        name="kimi-k2", model="kimi-k2-0905-preview",
        base_url="https://api.moonshot.ai/v1", api_key_env="MOONSHOT_API_KEY",
    ),
    "glm-4.6": lambda: OpenAICompatDriver(
        name="glm-4.6", model="glm-4.6",
        base_url="https://api.z.ai/api/paas/v4", api_key_env="ZAI_API_KEY",
    ),
    "gpt-frontier": lambda: OpenAICompatDriver(
        name="gpt-frontier", model="gpt-4o",
        base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY",
    ),
}


def build(name: str) -> Driver:
    if name not in REGISTRY:
        raise KeyError(f"unknown driver {name!r}; known={list(REGISTRY)}")
    return REGISTRY[name]()
