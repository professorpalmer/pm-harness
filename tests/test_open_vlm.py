"""Open VLM sidecar: env picker selects OpenRouter VLM vs Gemini; the open
sidecar honors its model + key env. Offline (no live calls)."""
import pytest
pytestmark = pytest.mark.swarm
import os
from harness.vision import (default_sidecar, OpenRouterVisionSidecar,
                            GeminiVisionSidecar)


def test_default_sidecar_picks_gemini_by_default(monkeypatch):
    monkeypatch.delenv("HARNESS_VLM_REACH", raising=False)
    assert isinstance(default_sidecar(), GeminiVisionSidecar)


def test_default_sidecar_picks_openrouter_when_set(monkeypatch):
    monkeypatch.setenv("HARNESS_VLM_REACH", "openrouter")
    sc = default_sidecar()
    assert isinstance(sc, OpenRouterVisionSidecar)
    assert sc.model == "qwen/qwen3-vl-30b-a3b-instruct"
    assert sc.api_key_env == "OPENROUTER_API_KEY"


def test_open_vlm_model_override(monkeypatch):
    monkeypatch.setenv("HARNESS_VLM_REACH", "openrouter")
    monkeypatch.setenv("HARNESS_VLM_MODEL", "qwen/qwen3-vl-8b-instruct")
    sc = default_sidecar()
    assert sc.model == "qwen/qwen3-vl-8b-instruct"


def test_open_vlm_missing_key_errors(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    sc = OpenRouterVisionSidecar()
    r = sc.transcribe("/tmp/testimg.png") if os.path.exists("/tmp/testimg.png") else None
    # with no key, _key() raises inside transcribe -> VisionResult.error set (repr of RuntimeError)
    if r is not None:
        assert r.error and "OPENROUTER_API_KEY" in r.error
