import json
import urllib.request
import urllib.error
import threading
from http.server import ThreadingHTTPServer
import pytest
from harness.config import HarnessConfig
from harness.conversation import ConversationalSession, ConvEvent

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

def test_interrupt_endpoint_token_guarded(tmp_path):
    httpd, port, srv = _server()
    srv._cfg.state_dir = str(tmp_path)
    
    try:
        # 1. POST /api/session/interrupt rejected without token
        try:
            _post(port, "/api/session/interrupt", {}, {"Content-Type": "application/json"})
            assert False, "should have failed with 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403

        # Reset _pilot's cancel flag
        srv._pilot._cancel.clear()
        assert not srv._pilot._cancel.is_set()

        # 2. POST /api/session/interrupt accepted with token
        resp = _post(port, "/api/session/interrupt", {}, {
            "Content-Type": "application/json",
            "X-Harness-Token": srv._TOKEN
        })
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("ok") is True
        
        # Verify it called interrupt() which sets _cancel
        assert srv._pilot._cancel.is_set()
    finally:
        httpd.shutdown()


def test_send_loop_with_cancel_preset_halts_quickly():
    config = HarnessConfig()
    session = ConversationalSession(config)
    
    class CancelOnCompletePilot:
        def complete(self, prompt, *, system=None):
            session._cancel.set()
            class R:
                text = '{"say": "acting", "actions": [{"kind": "read_file", "path": "AGENTS.md", "goal": "read rules"}]}'
                error = None
                tokens_out = 10
                tokens_in = 10
            return R()
            
    session.pilot = CancelOnCompletePilot()
    
    # When we call send(), it will call our custom pilot, which sets _cancel.
    # After the pilot turn, before executing the action, it should check _cancel and halt.
    events = list(session.send("hello"))
    
    interrupted_events = [ev for ev in events if ev.kind in ("interrupted", "halt")]
    assert len(interrupted_events) > 0
    # The action must not have executed (the action result event should not exist)
    action_result_events = [ev for ev in events if ev.kind == "action_result"]
    assert len(action_result_events) == 0
