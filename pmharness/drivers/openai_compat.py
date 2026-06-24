from __future__ import annotations

"""OpenAICompatDriver: drives any OpenAI-compatible chat endpoint. Kimi
(Moonshot), GLM (z.ai), OpenAI, and most open-weights providers all expose this
schema, so one driver covers the whole registry. stdlib-only (urllib) to keep
the rig dependency-light and auditable.

Keys are read from the environment at call time and never logged.
"""

import json
import os
import time
import urllib.request
import urllib.error

from .base import DriverResponse, SYSTEM_PROMPT


class OpenAICompatDriver:
    def __init__(
        self,
        name: str,
        model: str,
        base_url: str,
        api_key_env: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        timeout: int = 90,
        extra_headers: dict | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    def _key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"missing API key in env var {self.api_key_env}")
        return key

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        url = f"{self.base_url}/chat/completions"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": task_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._key()}",
        }
        headers.update(self.extra_headers)
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            return DriverResponse(
                text="", model=self.name, error=f"HTTP {e.code}: {detail}",
                latency_ms=(time.time() - t0) * 1000.0,
            )
        except Exception as e:  # network, timeout, json
            return DriverResponse(
                text="", model=self.name, error=repr(e),
                latency_ms=(time.time() - t0) * 1000.0,
            )

        latency = (time.time() - t0) * 1000.0
        try:
            text = raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return DriverResponse(
                text="", model=self.name, error=f"unexpected response shape: {str(raw)[:300]}",
                latency_ms=latency,
            )
        usage = raw.get("usage", {}) or {}
        return DriverResponse(
            text=text,
            tokens_in=int(usage.get("prompt_tokens", 0) or 0),
            tokens_out=int(usage.get("completion_tokens", 0) or 0),
            latency_ms=latency,
            model=self.name,
            meta={"raw_finish": raw["choices"][0].get("finish_reason") if raw.get("choices") else None},
        )
