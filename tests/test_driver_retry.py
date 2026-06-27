import io
import json
import urllib.request
import urllib.error
import pytest

from pmharness.drivers.openai_compat import OpenAICompatDriver
from pmharness.drivers.anthropic import AnthropicDriver
import pmharness.drivers.retry


def test_openai_driver_complete_retry(monkeypatch):
    driver = OpenAICompatDriver(
        name="test-driver",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    )
    driver._key = lambda: "fake-key"

    orig_with_retry = pmharness.drivers.retry.with_retry
    def mock_with_retry(fn, **kwargs):
        kwargs["sleep"] = lambda x: None
        return orig_with_retry(fn, **kwargs)
    monkeypatch.setattr(pmharness.drivers.retry, "with_retry", mock_with_retry)

    calls = 0
    def mock_urlopen(req, timeout=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            err_fp = io.BytesIO(b"Overloaded")
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, err_fp)
        
        resp_data = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Success content"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25
            }
        }
        res_fp = io.BytesIO(json.dumps(resp_data).encode("utf-8"))
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return res_fp.read()
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    resp = driver.complete("Hello")
    assert calls == 2
    assert resp.text == "Success content"
    assert resp.meta.get("retry_attempts") == 2


def test_anthropic_driver_complete_retry(monkeypatch):
    driver = AnthropicDriver(
        name="test-driver-anthropic",
        model="claude-3",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
    )
    driver._key = lambda: "fake-key"

    orig_with_retry = pmharness.drivers.retry.with_retry
    def mock_with_retry(fn, **kwargs):
        kwargs["sleep"] = lambda x: None
        return orig_with_retry(fn, **kwargs)
    monkeypatch.setattr(pmharness.drivers.retry, "with_retry", mock_with_retry)

    calls = 0
    def mock_urlopen(req, timeout=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            err_fp = io.BytesIO(b"Overloaded")
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, err_fp)
        
        resp_data = {
            "content": [{"type": "text", "text": "Anthropic content"}],
            "usage": {"input_tokens": 12, "output_tokens": 22},
            "stop_reason": "end_turn"
        }
        res_fp = io.BytesIO(json.dumps(resp_data).encode("utf-8"))
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                return res_fp.read()
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    resp = driver.complete("Hello")
    assert calls == 2
    assert resp.text == "Anthropic content"
    assert resp.meta.get("retry_attempts") == 2


def test_openai_driver_chat_stream_no_retry_after_delta(monkeypatch):
    driver = OpenAICompatDriver(
        name="test-driver",
        model="gpt-4o",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
    )
    driver._key = lambda: "fake-key"

    orig_with_retry = pmharness.drivers.retry.with_retry
    def mock_with_retry(fn, **kwargs):
        kwargs["sleep"] = lambda x: None
        return orig_with_retry(fn, **kwargs)
    monkeypatch.setattr(pmharness.drivers.retry, "with_retry", mock_with_retry)

    calls_to_urlopen = 0

    class FailingStreamResponse:
        def __init__(self):
            self.lines = [
                b"data: " + json.dumps({
                    "choices": [{
                        "delta": {
                            "content": "Hello"
                        }
                    }]
                }).encode("utf-8") + b"\n"
            ]
            self.idx = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.idx < len(self.lines):
                val = self.lines[self.idx]
                self.idx += 1
                return val
            err_fp = io.BytesIO(b"Overloaded")
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, err_fp)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=None):
        nonlocal calls_to_urlopen
        calls_to_urlopen += 1
        return FailingStreamResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    deltas = []
    def on_delta(d):
        deltas.append(d)

    resp = driver.chat_stream(
        messages=[{"role": "user", "content": "hi"}],
        on_delta=on_delta
    )

    assert calls_to_urlopen == 1
    assert deltas == ["Hello"]
    assert resp.error is not None
    assert "HTTP 503" in resp.error
    assert resp.meta.get("retry_attempts") == 1
