"""Live self-editing (Hermes-style) support: resume-across-restart signals.

These cover the backend half of the self-dev/restart loop -- the transcript
knows when a reply is owed (`has_pending_user_turn`), `/api/session/state`
surfaces that as `resume_pending` so the UI auto-continues after a backend
restart, and `/api/session/persist` flushes state before the process is
swapped. The actual `/api/restart` self-terminate is intentionally NOT exercised
in-process (it would SIGTERM the test runner); it is covered by the Electron IPC
path in the desktop app.
"""
import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer


def _make_session():
    from harness.conversation import ConversationalSession
    from harness.config import HarnessConfig
    return ConversationalSession(HarnessConfig())


def test_has_pending_user_turn_true_when_reply_owed():
    s = _make_session()
    s._history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    assert s.has_pending_user_turn() is True


def test_has_pending_user_turn_false_after_assistant_reply():
    s = _make_session()
    s._history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert s.has_pending_user_turn() is False


def test_has_pending_user_turn_false_on_empty_transcript():
    s = _make_session()
    s._history = [{"role": "system", "content": "sys"}]
    assert s.has_pending_user_turn() is False


def _spin_server():
    import harness.server as srv
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return srv, httpd, port


def test_session_state_reports_resume_pending():
    srv, httpd, port = _spin_server()
    saved = list(srv._pilot._history)
    try:
        # An unanswered user turn while idle -> resume_pending true.
        srv._pilot._history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "please continue"},
        ]
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/session/state?token={srv._TOKEN}", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        assert data["resume_pending"] is True

        # A completed turn (ends on assistant) -> no resume owed.
        srv._pilot._history.append({"role": "assistant", "content": "done"})
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/session/state?token={srv._TOKEN}", timeout=5)
        data = json.loads(resp.read().decode("utf-8"))
        assert data["resume_pending"] is False
    finally:
        srv._pilot._history = saved
        httpd.shutdown()


def test_session_persist_endpoint_writes_transcript(tmp_path):
    from harness.sessions import load_transcript
    srv, httpd, port = _spin_server()
    saved_hist = list(srv._pilot._history)
    saved_active = srv._sessions._active
    saved_state_dir = srv._cfg.state_dir
    try:
        srv._cfg.state_dir = str(tmp_path)
        srv._sessions._active = "sess-persist-test"
        srv._pilot._history = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "remember me"},
        ]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/session/persist?token={srv._TOKEN}",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Harness-Token": srv._TOKEN},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        assert resp.status == 200
        assert json.loads(resp.read().decode("utf-8"))["ok"] is True

        restored = load_transcript(str(tmp_path), "sess-persist-test")
        hist = restored.get("history") if isinstance(restored, dict) else restored
        assert any(m.get("content") == "remember me" for m in hist)
    finally:
        srv._pilot._history = saved_hist
        srv._sessions._active = saved_active
        srv._cfg.state_dir = saved_state_dir
        httpd.shutdown()
