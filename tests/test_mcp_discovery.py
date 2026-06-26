from unittest.mock import patch, MagicMock
import os
from harness.mcp_client import StdioMcpClient, McpTool
from harness.mcp_manager import McpManager
from harness.conversation import _format_mcp_tools_section


@patch("subprocess.Popen")
def test_stdio_mcp_client_env_filtering(mock_popen):
    original_environ = dict(os.environ)
    try:
        # Inject fake secret and baseline keys
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake-secret-123"
        os.environ["ANOTHER_SECRET"] = "some-key"
        os.environ["PATH"] = "/usr/bin:/bin"
        os.environ["HOME"] = "/Users/fake"
        os.environ["XDG_CONFIG_HOME"] = "/Users/fake/.config"
        os.environ["USER"] = "fakeuser"

        client = StdioMcpClient(
            name="test_server",
            command="node",
            args=["index.js"],
            env={"EXPLICIT_KEY": "explicit_val", "PATH": "/custom/path"}
        )

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdout.readline.return_value = '{"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "test-srv"}, "capabilities": {}}}\n'
        mock_proc.stderr = []
        mock_popen.return_value = mock_proc

        client.start()

        assert mock_popen.called
        kwargs = mock_popen.call_args[1]
        passed_env = kwargs.get("env", {})

        # Assert secret is filtered out
        assert "OPENROUTER_API_KEY" not in passed_env
        assert "ANOTHER_SECRET" not in passed_env

        # Assert baseline variables are preserved
        assert passed_env.get("HOME") == "/Users/fake"
        assert passed_env.get("XDG_CONFIG_HOME") == "/Users/fake/.config"
        assert passed_env.get("USER") == "fakeuser"

        # Assert custom server env updates are applied (taking precedence over base env)
        assert passed_env.get("EXPLICIT_KEY") == "explicit_val"
        assert passed_env.get("PATH") == "/custom/path"
    finally:
        os.environ.clear()
        os.environ.update(original_environ)


def test_prompt_catalog_builder_with_tools():
    mcp_mgr = McpManager()
    # 1. Zero tools -> empty string
    assert _format_mcp_tools_section(mcp_mgr) == ""
    assert _format_mcp_tools_section(None) == ""

    # 2. 1-2 fake tools -> formatted list
    tool1 = McpTool(
        server="github",
        name="create_issue",
        description="Create a new GitHub issue",
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array"}
            },
            "required": ["title"]
        }
    )
    tool2 = McpTool(
        server="filesystem",
        name="read_file",
        description="Read file contents",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    )

    with patch.object(McpManager, "discovered_tools", return_value=[tool1, tool2]):
        section = _format_mcp_tools_section(mcp_mgr)
        assert "## Connected MCP tools" in section
        assert "- github.create_issue: Create a new GitHub issue (args: title:string (required), body:string, labels:array)" in section
        assert "- filesystem.read_file: Read file contents (args: path:string (required))" in section
