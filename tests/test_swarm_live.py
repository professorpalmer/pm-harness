"""Tests for swarm live GET endpoint."""
import json
import threading
import urllib.request
import urllib.error
import tempfile
import shutil
import os
from http.server import ThreadingHTTPServer

import pytest

def _server(tmp_state_dir):
    import harness.server as srv
    # Set a temp state dir
    srv._session.state_dir = tmp_state_dir
    
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port, srv

def _get(port, path, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {}, method="GET")
    return urllib.request.urlopen(req, timeout=10)

def test_swarm_live_returns_expected_shape():
    tmp_dir = tempfile.mkdtemp()
    try:
        httpd, port, srv = _server(tmp_dir)
        try:
            # First try without token -> expect 403
            try:
                _get(port, "/api/swarm/live")
                assert False, "should have failed with 403"
            except urllib.error.HTTPError as e:
                assert e.code == 403

            # Try with valid token
            headers = {"X-Harness-Token": srv._TOKEN}
            resp = _get(port, "/api/swarm/live", headers=headers)
            assert resp.status == 200
            
            data = json.loads(resp.read().decode())
            
            # Verify keys in the returned shape
            assert "session" in data
            assert "jobs" in data
            
            session_data = data["session"]
            assert "tokens_used" in session_data
            assert "est_cost_usd" in session_data
            assert "driver" in session_data
            
            assert isinstance(session_data["tokens_used"], int)
            assert isinstance(session_data["est_cost_usd"], (int, float))
            assert isinstance(session_data["driver"], str)
            
            assert isinstance(data["jobs"], list)
        finally:
            httpd.shutdown()
    finally:
        shutil.rmtree(tmp_dir)
