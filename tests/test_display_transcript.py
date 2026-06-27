import os
import json
import tempfile
import pytest

from harness.config import HarnessConfig
from harness.conversation import ConversationalSession, ConvEvent
from harness.sessions import save_transcript, load_transcript

class MockDriverResponse:
    def __init__(self, text="", error=None, tokens_out=10):
        self.text = text
        self.error = error
        self.tokens_out = tokens_out
        self.meta = {}

class MockPilot:
    name = "mock"
    def __init__(self, return_text="Sure, I can help you with that."):
        self.return_text = return_text
        self.chat_calls = []

    def chat(self, messages, tools=None, system=None):
        self.chat_calls.append((messages, system))
        # Return a valid JSON envelope representation of pilot turn if not native,
        # or a clean text response.
        return MockDriverResponse(text='{"say": "Sure, I can help you with that.", "actions": []}')

def test_display_transcript_accumulation():
    cfg = HarnessConfig()
    session = ConversationalSession(cfg)
    session.pilot = MockPilot()  # type: ignore

    # Send a user message and run the pilot loop
    events = list(session.send("how do I build a wooden table?"))
    
    # Check that display transcript has correct user message and clean assistant message
    display = session.export_display_transcript()
    assert len(display) == 2
    assert display[0] == {"type": "message", "role": "user", "text": "how do I build a wooden table?"}
    assert display[1] == {"type": "message", "role": "assistant", "text": "Sure, I can help you with that."}

    # Verify that the raw history has the raw pilot output formatting
    history = session.export_history()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    # It has the full clean say text or the acting fallback
    assert history[1]["content"] == "Sure, I can help you with that."

def test_save_load_display_transcript_roundtrip(tmp_path):
    state_dir = str(tmp_path)
    session_id = "test-session-display"
    
    # Mock some display transcript and raw history data
    history_data = [
        {"role": "user", "content": "raw user message with system markers"},
        {"role": "assistant", "content": "raw assistant message"}
    ]
    display_data = [
        {"role": "user", "text": "clean user message"},
        {"role": "assistant", "text": "clean assistant message"}
    ]
    job_ids_data = ["job_1234567890ab", "local-12345678"]

    data = {
        "history": history_data,
        "display": display_data,
        "job_ids": job_ids_data
    }

    save_transcript(state_dir, session_id, data)

    # Verify JSON structure on disk
    p = tmp_path / "transcripts" / f"{session_id}.json"
    assert p.exists()
    
    loaded_data = json.loads(p.read_text(encoding="utf-8"))
    assert loaded_data["history"] == history_data
    assert loaded_data["display"] == display_data
    assert loaded_data["job_ids"] == job_ids_data

    # Load back using load_transcript
    loaded = load_transcript(state_dir, session_id)
    assert isinstance(loaded, dict)
    assert loaded["history"] == history_data
    assert loaded["display"] == display_data
    assert loaded["job_ids"] == job_ids_data

def test_load_history_handles_both_formats():
    cfg = HarnessConfig()
    
    # 1. New dictionary format
    session_new = ConversationalSession(cfg)
    history_data = [
        {"role": "user", "content": "raw user"},
        {"role": "assistant", "content": "raw assistant"}
    ]
    display_data = [
        {"role": "user", "text": "clean user"},
        {"role": "assistant", "text": "clean assistant"}
    ]
    job_ids_data = ["job_123"]
    
    session_new.load_history({
        "history": history_data,
        "display": display_data,
        "job_ids": job_ids_data
    })
    
    assert session_new.export_history() == history_data
    assert session_new.export_display_transcript() == display_data
    assert session_new._session_job_ids == job_ids_data

    # 2. Legacy list format (for backward compatibility)
    session_legacy = ConversationalSession(cfg)
    session_legacy.load_history(history_data)
    
    assert session_legacy.export_history() == history_data
    assert session_legacy.export_display_transcript() == []
    assert session_legacy._session_job_ids == []
