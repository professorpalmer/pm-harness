from __future__ import annotations

"""AnthropicDriver: Claude's native Messages API (/v1/messages) is NOT
OpenAI-compatible (different auth header, request shape, and response shape), so
it gets a dedicated driver. stdlib-only. Key read from env at call time.
"""

import json
import os
import time
import urllib.request
import urllib.error

from .base import DriverResponse, SYSTEM_PROMPT
from .retry import with_retry
from pmharness.reasoning import extract_reasoning, strip_think_blocks


class AnthropicDriver:
    supports_streaming = False

    def __init__(self, name: str, model: str, *,
                 base_url: str = "https://api.anthropic.com/v1",
                 api_key_env: str = "ANTHROPIC_API_KEY",
                 version: str = "2023-06-01",
                 max_tokens: int = 1024, temperature: float = 0.0, timeout: int = 90,
                 send_temperature: bool = False,
                 enable_prompt_cache: bool = True) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.version = version
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.send_temperature = send_temperature
        self.timeout = timeout
        self.enable_prompt_cache = enable_prompt_cache

    def _key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"missing API key in env var {self.api_key_env}")
        return key

    def complete(self, task_prompt: str, *, system: str = SYSTEM_PROMPT) -> DriverResponse:
        url = f"{self.base_url}/messages"
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": task_prompt}],
        }
        if self.enable_prompt_cache:
            body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        else:
            body["system"] = system

        # Some Anthropic models (Opus 4.x) reject an explicit temperature.
        if self.temperature is not None and self.send_temperature:
            body["temperature"] = self.temperature
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._key(),
            "anthropic-version": self.version,
        }
        if self.enable_prompt_cache:
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        def _call() -> DriverResponse:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:500]
                return DriverResponse(text="", model=self.name, error=f"HTTP {e.code}: {detail}",
                                      latency_ms=(time.time() - t0) * 1000.0)
            except Exception as e:
                return DriverResponse(text="", model=self.name, error=repr(e),
                                      latency_ms=(time.time() - t0) * 1000.0)
            latency = (time.time() - t0) * 1000.0
            try:
                # content is a list of blocks; take the first text block
                blocks = raw.get("content", [])
                text = ""
                for b in blocks:
                    if b.get("type") == "text":
                        text = b.get("text", "")
                        break
            except (AttributeError, TypeError):
                return DriverResponse(text="", model=self.name,
                                      error=f"unexpected response: {str(raw)[:300]}", latency_ms=latency)
            usage = raw.get("usage", {}) or {}
            cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
            cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
            return DriverResponse(
                text=text,
                tokens_in=int(usage.get("input_tokens", 0) or 0),
                tokens_out=int(usage.get("output_tokens", 0) or 0),
                latency_ms=latency, model=self.name,
                meta={
                    "stop_reason": raw.get("stop_reason"),
                    "cache_write_tokens": cache_write,
                    "cache_read_tokens": cache_read,
                },
            )

        return with_retry(_call)

    def chat(self, messages: list, *, tools: list | None = None, system: str | None = None) -> DriverResponse:
        url = f"{self.base_url}/messages"

        anthropic_msgs = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                continue

            blocks = []
            if role == "assistant":
                text = msg.get("content") or ""
                if text:
                    blocks.append({"type": "text", "text": text})
                tool_calls = msg.get("tool_calls") or []
                for tc in tool_calls:
                    tc_id = tc.get("id") or ""
                    func = tc.get("function") or {}
                    name = func.get("name") or ""
                    raw_args = func.get("arguments") or {}
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            args = {}
                    else:
                        args = raw_args
                    blocks.append({
                        "type": "tool_use",
                        "id": tc_id,
                        "name": name,
                        "input": args
                    })
                anth_role = "assistant"

            elif role == "tool":
                tc_id = msg.get("tool_call_id") or ""
                content_val = msg.get("content") or ""
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tc_id,
                    "content": content_val
                })
                anth_role = "user"

            else:
                text = msg.get("content") or ""
                blocks.append({"type": "text", "text": text})
                anth_role = "user"

            if anthropic_msgs and anthropic_msgs[-1]["role"] == anth_role:
                anthropic_msgs[-1]["content"].extend(blocks)
            else:
                if not blocks:
                    blocks = [{"type": "text", "text": ""}]
                anthropic_msgs.append({
                    "role": anth_role,
                    "content": blocks
                })

        anthropic_tools = []
        if tools:
            for t in tools:
                if not isinstance(t, dict):
                    continue
                func = t.get("function") or {}
                name = func.get("name") or ""
                desc = func.get("description") or ""
                schema = func.get("parameters") or {"type": "object", "properties": {}, "required": []}
                anthropic_tools.append({
                    "name": name,
                    "description": desc,
                    "input_schema": schema
                })

        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_msgs,
        }

        if system:
            if self.enable_prompt_cache:
                body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            else:
                body["system"] = system

        if self.temperature is not None and self.send_temperature:
            body["temperature"] = self.temperature

        if anthropic_tools:
            body["tools"] = anthropic_tools
            body["tool_choice"] = {"type": "auto"}

        data = json.dumps(body).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._key(),
            "anthropic-version": self.version,
        }
        if self.enable_prompt_cache:
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"

        def _call() -> DriverResponse:
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
            except Exception as e:
                return DriverResponse(
                    text="", model=self.name, error=repr(e),
                    latency_ms=(time.time() - t0) * 1000.0,
                )

            latency = (time.time() - t0) * 1000.0

            try:
                blocks = raw.get("content") or []
                text_pieces = []
                tool_calls = []

                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    b_type = b.get("type")
                    if b_type == "text":
                        text_pieces.append(b.get("text") or "")
                    elif b_type == "tool_use":
                        tc_id = b.get("id") or ""
                        name = b.get("name") or ""
                        input_dict = b.get("input") or {}
                        tool_calls.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(input_dict)
                            }
                        })

                full_text = "".join(text_pieces)

            except (AttributeError, TypeError):
                return DriverResponse(
                    text="", model=self.name,
                    error=f"unexpected response: {str(raw)[:300]}", latency_ms=latency
                )

            message_obj = {"content": blocks}
            reasoning = extract_reasoning(message_obj)
            if not reasoning:
                reasoning = extract_reasoning({"content": full_text})

            pure_text = strip_think_blocks(full_text)

            usage = raw.get("usage", {}) or {}
            cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
            cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)

            return DriverResponse(
                text=pure_text,
                tokens_in=int(usage.get("input_tokens", 0) or 0),
                tokens_out=int(usage.get("output_tokens", 0) or 0),
                latency_ms=latency,
                model=self.name,
                meta={
                    "tool_calls": tool_calls,
                    "reasoning": reasoning,
                    "finish_reason": raw.get("stop_reason") or "",
                    "cache_write_tokens": cache_write,
                    "cache_read_tokens": cache_read,
                }
            )

        return with_retry(_call)
