"""Tests for workspace open and session binding behavior (no network)."""
import json
import threading
import urllib.request
import urllib.error
import os
from http.server import ThreadingHTTPServer

import pytest
from harness.sessions import save_transcript, load_transcript


def _server():
    import harness.server as srv
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port, srv


def _post(port, path, body, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                 data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=10)


def test_workspace_session_binding(tmp_path):
    httpd, port, srv = _server()
    # Override server's state_dir with a temporary one to avoid reading/writing real user data
    srv._cfg.state_dir = str(tmp_path)
    srv._sessions.path = str(tmp_path / "harness_sessions.json")
    srv._sessions._sessions = []
    srv._sessions._active = None

    try:
        # Create temporary project directories A and B
        repo_a = tmp_path / "repo_a"
        repo_a.mkdir()
        repo_b = tmp_path / "repo_b"
        repo_b.mkdir()

        # Step 1: Open project A, which will create a fresh session for it
        # (or we can create and switch to it first)
        resp1 = _post(port, "/api/workspace/open", {"path": str(repo_a)},
                      {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN})
        assert resp1.status == 200
        data1 = json.loads(resp1.read().decode())
        assert data1["ok"] is True
        
        # Get active session for project A
        session_a_id = srv._sessions.active
        assert session_a_id is not None
        
        # Check that the session is bound to repo A
        sessions_list = srv._sessions.list()
        sess_a = next(s for s in sessions_list if s["id"] == session_a_id)
        assert sess_a["repo"] == str(repo_a)

        # Set some conversation history in pilot for session A
        transcript_a = [
            {"role": "user", "content": "hello in repo a"},
            {"role": "assistant", "content": "response in repo a"}
        ]
        # In memory _pilot history has system prompt at index 0, so load_history expects list of turns.
        srv._pilot.load_history(transcript_a)

        # Step 2: Open project B while session A is active
        resp2 = _post(port, "/api/workspace/open", {"path": str(repo_b)},
                      {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN})
        assert resp2.status == 200
        data2 = json.loads(resp2.read().decode())
        assert data2["ok"] is True

        # (a) Verify opening project B did NOT change project A's session.repo (no re-stamp)
        sessions_list = srv._sessions.list()
        sess_a_refreshed = next(s for s in sessions_list if s["id"] == session_a_id)
        assert sess_a_refreshed["repo"] == str(repo_a)

        # (b) Verify opening project B switched active to a B-bound session (freshly created one)
        session_b_id = srv._sessions.active
        assert session_b_id is not None
        assert session_b_id != session_a_id
        
        sess_b = next(s for s in sessions_list if s["id"] == session_b_id)
        assert sess_b["repo"] == str(repo_b)

        # (c) Verify outgoing A conversation transcript was saved
        saved_transcript_a = load_transcript(str(tmp_path), session_a_id)
        # Check that it contains the content we set in step 1
        assert saved_transcript_a is not None
        assert saved_transcript_a["history"] == transcript_a

        # Set some history in project B session
        transcript_b = [
            {"role": "user", "content": "hello in repo b"}
        ]
        srv._pilot.load_history(transcript_b)
        
        # Step 3: Open project A again
        resp3 = _post(port, "/api/workspace/open", {"path": str(repo_a)},
                      {"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN})
        assert resp3.status == 200
        data3 = json.loads(resp3.read().decode())
        assert data3["ok"] is True

        # (d) Verify opening A again returns to the A-bound session, and loads the original conversation
        assert srv._sessions.active == session_a_id
        
        # Verify srv._pilot history contains the loaded project A messages
        # export_history returns the raw turns (without system prompt)
        assert srv._pilot.export_history() == transcript_a

    finally:
        httpd.shutdown()
