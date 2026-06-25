"""HTTP MCP transport against an in-process fake JSON-RPC HTTP server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness.mcp_http_client import HttpMcpClient
from harness.mcp_manager import McpManager

TOOLS = [{"name": "ping", "description": "returns pong",
          "inputSchema": {"type": "object", "properties": {}}}]


class _FakeMcpHTTP(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        msg = json.loads(self.rfile.read(n).decode() or "{}")
        mid, method = msg.get("id"), msg.get("method")
        def send(obj):
            data = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "fakehttp", "version": "1.0"}}})
        elif method == "notifications/initialized":
            self.send_response(202); self.end_headers()
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": "pong"}], "isError": False}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "nope"}})


def _server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeMcpHTTP)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/rpc"


def test_http_client_handshake_list_call():
    httpd, url = _server()
    try:
        c = HttpMcpClient(name="fakehttp", url=url)
        c.start()
        assert c.alive
        tools = c.list_tools()
        assert [t.name for t in tools] == ["ping"]
        out = c.call_tool("ping", {})
        assert out["content"][0]["text"] == "pong"
    finally:
        httpd.shutdown()


def test_manager_routes_url_to_http(tmp_path):
    httpd, url = _server()
    try:
        m = McpManager(config_path=str(tmp_path / "mcp.json"))
        m.save_server("fakehttp", {"url": url})
        tools = m.start_server("fakehttp")
        assert [t.name for t in tools] == ["ping"]
        st = m.status()[0]
        assert st["transport"] == "http" and st["running"]
        out = m.call("fakehttp.ping", {})
        assert out["content"][0]["text"] == "pong"
    finally:
        m.stop_all(); httpd.shutdown()
