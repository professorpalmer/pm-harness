"""Tests for pilot reachability (Gemini native and MoA planner virtual model)."""
import os
from harness import providers as prov
from pmharness.drivers.gemini import GeminiDriver
from pmharness.drivers.moa import MoADriver
from pmharness.drivers.anthropic import AnthropicDriver
from pmharness.drivers.openai_compat import OpenAICompatDriver


def test_native_gemini_reachability(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    
    pilots = prov.available_pilots()
    assert "gemini:gemini-3.5-flash" in pilots

    d1 = prov.build_pilot("gemini:gemini-3.5-flash")
    assert isinstance(d1, GeminiDriver)
    assert d1.model == "gemini-3.5-flash"
    assert d1.api_key_env == "GEMINI_API_KEY"

    d2 = prov.build_pilot("gemini-3.5-flash")
    assert isinstance(d2, GeminiDriver)
    assert d2.model == "gemini-3.5-flash"
    assert d2.api_key_env == "GEMINI_API_KEY"


def test_moa_reachability(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")

    pilots = prov.available_pilots()
    # MoA is a planner/review virtual model and CANNOT act as the tool-calling
    # executor (selecting it as the pilot produced a hard runtime error), so it
    # is deliberately NOT offered in the pilot picker.
    assert "moa:moa-planner" not in pilots
    assert "moa-planner" not in pilots

    # It is still CONSTRUCTIBLE for planner/review use -- build_pilot accepts the
    # moa spec and returns a MoADriver; it just is not an interactive driver.
    d1 = prov.build_pilot("moa-planner")
    assert isinstance(d1, MoADriver)
    assert d1.name == "moa-planner"
    assert d1.reach == "openrouter"

    d2 = prov.build_pilot("moa:moa-planner")
    assert isinstance(d2, MoADriver)
    assert d2.name == "moa-planner"
    assert d2.reach == "openrouter"


def test_existing_behavior_intact(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-or-key")

    d1 = prov.build_pilot("anthropic:claude-opus-4-8")
    assert isinstance(d1, AnthropicDriver)
    assert d1.model == "claude-opus-4-8"

    d2 = prov.build_pilot("openrouter:qwen/qwen3-coder-30b-a3b-instruct")
    assert isinstance(d2, OpenAICompatDriver)
    assert "qwen3-coder-30b" in d2.model
