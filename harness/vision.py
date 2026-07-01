from __future__ import annotations

"""Vision sidecar: decouples image input from the driver.

The research found the only vision-capable open DRIVER (Kimi) is also the
weakest driver -- so the harness must NOT require the driver to have vision.
Instead a cheap VLM sidecar transcribes an image into a TEXT description once;
that text is prepended to the driver's context as durable signal. Any text-only
driver (glm-5.2, deepseek, qwen) then "sees" the image through the transcription.

This matches the kernel philosophy: the harness owns vision as a preprocessing
capability (like CodeGraph injection); the driver only ever reasons over text.
The image is processed ONCE, never re-sent through every driver call.

The sidecar is resolved dynamically from whatever provider key the user already
has (see default_sidecar). A user who configured only Anthropic, OpenAI, or xAI
still gets image input -- vision no longer requires a dedicated Gemini/OpenRouter
key. If no vision-capable provider is configured, transcription returns a clear,
actionable error instead of a cryptic missing-key failure.
"""

import base64
import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


_VLM_PROMPT = (
    "Transcribe and describe this image for a text-only coding agent. If it is a "
    "screenshot, UI, diagram, or document, capture the visible text verbatim and "
    "describe the layout/structure. Be precise and complete; the agent cannot see "
    "the image, only your text. Do not speculate beyond what is visible."
)


@dataclass
class VisionResult:
    text: str
    tokens_out: int = 0
    latency_ms: float = 0.0
    model: str = ""
    error: Optional[str] = None


def _media_type(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"): return "image/png"
    if p.endswith((".jpg", ".jpeg")): return "image/jpeg"
    if p.endswith(".webp"): return "image/webp"
    if p.endswith(".gif"): return "image/gif"
    return "image/png"


def _read_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{_media_type(image_path)};base64,{b64}"


class OpenAICompatVisionSidecar:
    """VLM transcription via any OpenAI-compatible /chat/completions endpoint.
    One transport covers OpenRouter, OpenAI, Gemini (openai-compat), xAI, and
    friends -- only base_url, model, and the key env differ. Contract: an image
    path in, a VisionResult (text) out."""

    def __init__(self, *, model: str, base_url: str, api_key_env: str,
                 timeout: int = 60) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.name = f"vlm:{model}"

    def _key(self) -> str:
        k = os.environ.get(self.api_key_env, "").strip()
        if not k:
            raise RuntimeError(f"missing VLM key in {self.api_key_env}")
        return k

    def transcribe(self, image_path: str) -> VisionResult:
        data_url = _read_data_url(image_path)
        body = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _VLM_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            "max_tokens": 800,
        }
        try:
            _auth = self._key()
        except Exception as e:
            return VisionResult("", error=repr(e), model=self.name)
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {_auth}"},
            method="POST")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = json.load(r)
        except urllib.error.HTTPError as e:
            return VisionResult("", error=f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}",
                                latency_ms=(time.time()-t0)*1000, model=self.name)
        except Exception as e:
            return VisionResult("", error=repr(e), latency_ms=(time.time()-t0)*1000, model=self.name)
        try:
            text = raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return VisionResult("", error=f"bad VLM response: {str(raw)[:200]}",
                                latency_ms=(time.time()-t0)*1000, model=self.name)
        usage = raw.get("usage", {}) or {}
        return VisionResult(text=text, tokens_out=int(usage.get("completion_tokens", 0) or 0),
                            latency_ms=(time.time()-t0)*1000, model=self.name)


class GeminiVisionSidecar(OpenAICompatVisionSidecar):
    """VLM transcription via Gemini's OpenAI-compatible endpoint (vision-capable).
    A stand-in for an open VLM sidecar (GLM-OCR / Kimi-VL / Qwen-VL) -- same
    contract: image path -> text. Swap base_url/model/key to use an open VLM."""

    def __init__(self, *, model: str = "gemini-3.1-flash-lite-preview",
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai",
                 api_key_env: str = "GEMINI_API_KEY", timeout: int = 60) -> None:
        super().__init__(model=model, base_url=base_url, api_key_env=api_key_env,
                         timeout=timeout)


class OpenRouterVisionSidecar(OpenAICompatVisionSidecar):
    """VLM transcription via an OPEN vision model on OpenRouter -- so vision is
    open-weights too, closing the last frontier-model dependency. Default model
    is qwen3-vl-30b-a3b (Apache-2.0, pairs with the qwen3-coder driver). Same
    image->text contract; swap model via HARNESS_VLM_MODEL.
    """

    def __init__(self, *, model: str = "qwen/qwen3-vl-30b-a3b-instruct",
                 base_url: str = "https://openrouter.ai/api/v1",
                 api_key_env: str = "OPENROUTER_API_KEY", timeout: int = 60) -> None:
        super().__init__(model=model, base_url=base_url, api_key_env=api_key_env,
                         timeout=timeout)


class AnthropicVisionSidecar:
    """VLM transcription via Anthropic's /v1/messages API (Claude is vision-capable).
    Anthropic uses a different wire format than OpenAI-compat providers -- image
    content blocks with base64 source -- so it needs its own transport. Used when
    the user's only configured provider is Anthropic (or MiniMax's anthropic-mode
    endpoint). Same image->text contract as the OpenAI-compat sidecar."""

    def __init__(self, *, model: str, base_url: str = "https://api.anthropic.com",
                 api_key_env: str = "ANTHROPIC_API_KEY", timeout: int = 60,
                 anthropic_version: str = "2023-06-01") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.anthropic_version = anthropic_version
        self.name = f"vlm:{model}"

    def _key(self) -> str:
        k = os.environ.get(self.api_key_env, "").strip()
        if not k:
            raise RuntimeError(f"missing VLM key in {self.api_key_env}")
        return k

    def transcribe(self, image_path: str) -> VisionResult:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = {
            "model": self.model,
            "max_tokens": 800,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": _VLM_PROMPT},
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": _media_type(image_path),
                        "data": b64,
                    }},
                ],
            }],
        }
        try:
            _auth = self._key()
        except Exception as e:
            return VisionResult("", error=repr(e), model=self.name)
        req = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "x-api-key": _auth,
                     "anthropic-version": self.anthropic_version},
            method="POST")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = json.load(r)
        except urllib.error.HTTPError as e:
            return VisionResult("", error=f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}",
                                latency_ms=(time.time()-t0)*1000, model=self.name)
        except Exception as e:
            return VisionResult("", error=repr(e), latency_ms=(time.time()-t0)*1000, model=self.name)
        try:
            blocks = raw.get("content", []) or []
            text = next((b.get("text", "") for b in blocks if b.get("type") == "text"), "")
        except (AttributeError, TypeError):
            return VisionResult("", error=f"bad VLM response: {str(raw)[:200]}",
                                latency_ms=(time.time()-t0)*1000, model=self.name)
        usage = raw.get("usage", {}) or {}
        return VisionResult(text=text, tokens_out=int(usage.get("output_tokens", 0) or 0),
                            latency_ms=(time.time()-t0)*1000, model=self.name)


class NullVisionSidecar:
    """Returned when no vision-capable provider key is configured. transcribe()
    yields a clear, actionable error so the UI can tell the user exactly how to
    enable image input -- instead of a cryptic missing-key failure."""

    name = "vlm:none"

    def transcribe(self, image_path: str) -> VisionResult:
        return VisionResult(
            "", model=self.name,
            error=("no vision-capable provider configured -- add an API key for "
                   "Anthropic, OpenAI, Google Gemini, xAI, or OpenRouter to enable "
                   "image input (or set HARNESS_VLM_REACH=openrouter)"))


def provider_vision_sidecar():
    """Build a sidecar from the first configured provider that has a vision model.
    Reuses the key the user already set, so image input works with zero extra
    setup. Returns None if no available provider declares a vision model."""
    try:
        from .providers import available_providers
    except Exception:
        return None
    for p in available_providers():
        model = getattr(p, "vision_model", "") or ""
        if not model:
            continue
        key_env = p.key_env()
        if not key_env:
            continue
        if p.api_mode == "anthropic_messages":
            return AnthropicVisionSidecar(model=model, base_url=p.base_url,
                                          api_key_env=key_env)
        return OpenAICompatVisionSidecar(model=model, base_url=p.base_url,
                                         api_key_env=key_env)
    return None


def transcribe_images(paths: list, sidecar=None) -> list:
    """Transcribe a list of image paths into VisionResults. Picks the sidecar
    from env / configured provider keys (see default_sidecar) if none provided."""
    sc = sidecar or default_sidecar()
    return [sc.transcribe(p) for p in paths]


def default_sidecar():
    """Resolve the vision sidecar. Precedence:

    1. Explicit reach override (HARNESS_VLM_REACH=openrouter -> open VLM,
       model overridable via HARNESS_VLM_MODEL).
    2. Dedicated VLM keys, preferring Gemini then OpenRouter (back-compat: these
       are the historical vision keys and keep their default models).
    3. Any other configured provider that declares a vision model (Anthropic,
       OpenAI, xAI, ...), reusing the key the user already has.
    4. Nothing configured -> NullVisionSidecar (actionable error, not a crash).
    """
    reach = os.environ.get("HARNESS_VLM_REACH", "").lower()
    if reach == "openrouter":
        model = os.environ.get("HARNESS_VLM_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")
        return OpenRouterVisionSidecar(model=model)
    if reach == "gemini":
        return GeminiVisionSidecar()

    if os.environ.get("GEMINI_API_KEY", "").strip():
        return GeminiVisionSidecar()
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        model = os.environ.get("HARNESS_VLM_MODEL", "qwen/qwen3-vl-30b-a3b-instruct")
        return OpenRouterVisionSidecar(model=model)

    sidecar = provider_vision_sidecar()
    if sidecar is not None:
        return sidecar
    return NullVisionSidecar()
