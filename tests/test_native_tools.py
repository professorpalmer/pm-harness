from __future__ import annotations
import json
import tempfile
import pytest
from typing import Any, Optional

from pmharness.reasoning import extract_reasoning
from pmharness.drivers.stub import StubDriver
from harness.pilot import build_tools_schema, parse_tool_calls, PilotAction, PilotTurn, PilotError
from harness.config import HarnessConfig
from harness.conversation import ConversationalSession, ConvEvent


class FakeMcpTool:
    def __init__(self, server: str, name: str, description: str, input_schema: dict):
        self.server = server
        self.name = name
        self.description = description
        self.input_schema = input_schema


def test_build_tools_schema():
    # Call build_tools_schema with built-ins only
    schemas = build_tools_schema()
    names = [s["function"]["name"] for s in schemas]
    assert "read_file" in names
    assert "write_file" in names
    assert "run_command" in names
    assert "list_dir" in names
    assert "web_search" in names
    assert "web_fetch" in names
    assert "read_pdf" in names
    assert "run_swarm" in names

    # Call with MCP tools
    fake_tool = FakeMcpTool(
        server="todo",
        name="add_item",
        description="Add a todo item",
        input_schema={
            "type": "object",
            "properties": {"item": {"type": "string"}},
            "required": ["item"]
        }
    )
    schemas_mcp = build_tools_schema([fake_tool])
    mcp_names = [s["function"]["name"] for s in schemas_mcp]
    assert "mcp_todo_add_item" in mcp_names
    mcp_schema = [s for s in schemas_mcp if s["function"]["name"] == "mcp_todo_add_item"][0]
    assert mcp_schema["function"]["description"] == "Add a todo item"
    assert mcp_schema["function"]["parameters"]["required"] == ["item"]


def test_parse_tool_calls():
    # Standard tool call
    tc_read = [
        {
            "id": "tc1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({"path": "src/main.py"})
            }
        }
    ]
    actions = parse_tool_calls(tc_read)
    assert len(actions) == 1
    assert actions[0].kind == "read_file"
    assert actions[0].path == "src/main.py"
    assert actions[0].tool_call_id == "tc1"

    # MCP tool call
    tc_mcp = [
        {
            "id": "tc2",
            "type": "function",
            "function": {
                "name": "mcp_weather_get_forecast",
                "arguments": json.dumps({"location": "New York"})
            }
        }
    ]
    actions_mcp = parse_tool_calls(tc_mcp)
    assert len(actions_mcp) == 1
    assert actions_mcp[0].kind == "call_mcp"
    assert actions_mcp[0].tool == "weather.get_forecast"
    assert actions_mcp[0].arguments == {"location": "New York"}
    assert actions_mcp[0].tool_call_id == "tc2"


def test_extract_reasoning():
    # Case 1: Direct reasoning field
    msg1 = {"reasoning": "I think this is step 1."}
    assert extract_reasoning(msg1) == "I think this is step 1."

    # Case 2: Direct reasoning_content field
    msg2 = {"reasoning_content": "I think this is step 2."}
    assert extract_reasoning(msg2) == "I think this is step 2."

    # Case 3: reasoning_details field (OpenRouter array of objects)
    msg3 = {
        "reasoning_details": [
            {"type": "thinking", "thinking": "Step 3 details."}
        ]
    }
    assert extract_reasoning(msg3) == "Step 3 details."

    # Case 4: Inline <think> tag fallback
    msg4 = {"content": "Hello! <think>Inside the think block.</think> Some prose."}
    assert extract_reasoning(msg4) == "Inside the think block."

    # None case
    msg_empty = {"content": "Hello! Just prose."}
    assert extract_reasoning(msg_empty) == ""


def test_stub_driver_chat():
    driver = StubDriver()
    
    # First turn: should emit a deterministic tool call
    messages1 = [{"role": "user", "content": "How are you?"}]
    resp1 = driver.chat(messages1)
    assert resp1.meta["tool_calls"] is not None
    assert len(resp1.meta["tool_calls"]) == 1
    assert resp1.meta["tool_calls"][0]["function"]["name"] == "read_file"
    assert resp1.text == ""

    # Subsequent turn: has tool call in history, should return prose content
    messages2 = [
        {"role": "user", "content": "How are you?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": resp1.meta["tool_calls"]
        },
        {"role": "tool", "tool_call_id": "call_stub_1", "content": "File content"}
    ]
    resp2 = driver.chat(messages2)
    assert not resp2.meta.get("tool_calls")
    assert "Based on the tool execution" in resp2.text


class _FakeNativePilot:
    name = "fake-native-pilot"
    
    def __init__(self):
        self.calls = 0

    def complete(self, task_prompt: str, *, system: Optional[str] = None) -> Any:
        # Dummy to satisfy Driver interface
        from pmharness.drivers.openai_compat import DriverResponse
        return DriverResponse(text="")

    def chat(self, messages: list, *, tools: list | None = None, system: str | None = None) -> Any:
        from pmharness.drivers.openai_compat import DriverResponse
        self.calls += 1
        if self.calls == 1:
            # Emit a tool call in turn 1
            tool_calls = [
                {
                    "id": "tc_smoke_1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": json.dumps({"path": "AGENTS.md"})
                    }
                }
            ]
            return DriverResponse(
                text="",
                tokens_out=15,
                latency_ms=1.0,
                meta={
                    "tool_calls": tool_calls,
                    "reasoning": "Need to check AGENTS.md first.",
                    "finish_reason": "tool_calls"
                }
            )
        else:
            # Emit final answer in turn 2
            return DriverResponse(
                text="I have read AGENTS.md and verified everything is fine.",
                tokens_out=20,
                latency_ms=1.0,
                meta={
                    "tool_calls": [],
                    "reasoning": "Already read it, now answering.",
                    "finish_reason": "stop"
                }
            )


def test_conversation_smoke_native_turn(monkeypatch):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp(), repo=tempfile.mkdtemp())
    s = ConversationalSession(cfg)
    s.pilot = _FakeNativePilot()

    events = list(s.send("Please read AGENTS.md for me."))
    kinds = [e.kind for e in events]
    
    # Assert events emitted
    assert "thinking" in kinds
    assert "action_start" in kinds
    assert "action_result" in kinds
    assert "message" in kinds
    assert kinds[-1] == "assistant_done"

    # Verify history structure: role: tool message was appended
    tool_msgs = [m for m in s._history if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc_smoke_1"
    # Since AGENTS.md won't exist in the temp repo, it should have a "File not found" error string
    assert "File not found" in tool_msgs[0]["content"]

    # Verify assistant message has native tool_calls
    assistant_with_tools = [m for m in s._history if m.get("role") == "assistant" and m.get("tool_calls")]
    assert len(assistant_with_tools) == 1
    assert assistant_with_tools[0]["tool_calls"][0]["id"] == "tc_smoke_1"
