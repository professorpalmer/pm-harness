"""Tests for driver re-resolution: the app must never default to a driver whose
provider is unavailable (e.g. saved driver qwen3-coder-30b routing through a
disconnected OpenRouter).

These test the _resolve_available_driver / _driver_provider_available helpers
directly against a saved _cfg, without reloading harness.server (which would
mutate shared module globals and leak into other tests)."""
import os
import json
import tempfile
import pytest

import harness.server as srv
from harness.config import HarnessConfig


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Snapshot + restore harness.server's module-level _cfg around each test so
    driver mutations never leak into other tests."""
    monkeypatch.setenv("HARNESS_STATE_DIR", tempfile.mkdtemp())
    saved = srv._cfg
    yield
    srv._cfg = saved


def _install_cfg(monkeypatch, enabled, driver, disconnect=None):
    state = os.environ["HARNESS_STATE_DIR"]
    json.dump({"enabled": enabled}, open(os.path.join(state, "models.json"), "w"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-...rted")
    import importlib
    from harness import keys as K
    importlib.reload(K)
    if disconnect:
        for d in disconnect:
            K.mark_disconnected(d)
    srv._cfg = HarnessConfig(driver=driver, reach="openrouter", state_dir=state)


def test_bare_driver_resolves_when_reach_disconnected(monkeypatch):
    _install_cfg(monkeypatch,
                 enabled=["anthropic:claude-opus-4-8", "anthropic:claude-sonnet-4-5"],
                 driver="qwen3-coder-30b",
                 disconnect=["openrouter"])
    srv._resolve_available_driver()
    assert srv._cfg.driver != "qwen3-coder-30b"
    assert srv._driver_provider_available(srv._cfg.driver)
    assert srv._cfg.driver.startswith("anthropic:")


def test_available_driver_is_left_alone(monkeypatch):
    _install_cfg(monkeypatch,
                 enabled=["anthropic:claude-opus-4-8"],
                 driver="anthropic:claude-opus-4-8",
                 disconnect=["openrouter"])
    srv._resolve_available_driver()
    assert srv._cfg.driver == "anthropic:claude-opus-4-8"


def test_provider_spec_driver_resolves_when_disconnected(monkeypatch):
    _install_cfg(monkeypatch,
                 enabled=["anthropic:claude-opus-4-8", "openrouter:openai/gpt-5.5"],
                 driver="openrouter:openai/gpt-5.5",
                 disconnect=["openrouter"])
    srv._resolve_available_driver()
    assert srv._driver_provider_available(srv._cfg.driver)
    assert srv._cfg.driver.startswith("anthropic:")
