#!/usr/bin/env python3
"""A minimal fake MCP stdio server for tests. Implements initialize, tools/list,
tools/call over newline-delimited JSON-RPC. Zero deps, py3.9-safe."""
import json, sys

TOOLS = [{"name": "echo", "description": "Echo back the text",
          "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
         {"name": "add", "description": "Add two numbers",
          "inputSchema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}}]

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake", "version": "1.0"}}})
        elif method == "notifications/initialized":
            pass  # notification, no reply
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            p = msg.get("params", {})
            name = p.get("name"); args = p.get("arguments", {})
            if name == "echo":
                out = args.get("text", "")
            elif name == "add":
                out = str(args.get("a", 0) + args.get("b", 0))
            else:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "no such tool"}}); continue
            send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": out}], "isError": False}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}})

if __name__ == "__main__":
    main()
