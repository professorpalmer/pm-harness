"""Pilot -> call_mcp -> MCP manager end-to-end (fake stdio server, no network)."""
import sys
from pathlib import Path

import pytest
pytestmark = pytest.mark.swarm  # constructs a ConversationalSession (pilot build)

from harness.config import HarnessConfig
from harness.conversation import ConversationalSession
from harness.mcp_manager import McpManager
from pmharness.drivers.openai_compat import DriverResponse

FAKE = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


class _McpPilot:
    """Says it'll use a tool, fires one call_mcp, then finishes."""
    name = "mcp-pilot"
    def __init__(self): self.n = 0
    def complete(self, prompt, *, system=None):
        self.n += 1
        if self.n == 1:
            t = '{"say":"calling echo","actions":[{"kind":"call_mcp","tool":"fake.echo","arguments":{"text":"pong"}}]}'
        else:
            t = '{"say":"Done.","actions":[]}'
        return DriverResponse(text=t, tokens_out=10, latency_ms=1.0)


def test_pilot_calls_mcp_tool(tmp_path):
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=str(tmp_path))
    s = ConversationalSession(cfg)
    s.pilot = _McpPilot()
    m = McpManager(config_path=str(tmp_path / "mcp.json"))
    m.save_server("fake", {"command": sys.executable, "args": [FAKE]})
    m.start_server("fake")
    s._mcp = m
    try:
        events = list(s.send("use the echo tool"))
        results = [e for e in events if e.kind == "action_result"]
        assert results, "expected an action_result from the mcp call"
        assert results[0].data.get("adapter") == "mcp"
        assert "pong" in results[0].data["artifacts"][0]["headline"]
    finally:
        m.stop_all()
