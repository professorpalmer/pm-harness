"""Finish-path hardening regression: the end-of-turn bookkeeping tail
(_finalize_turn) must never propagate an exception. A serialization error in
export_transcript_data() or a misbehaving postRun hook previously broke the
streaming response at finish-time and could strand the backend. These are
hermetic -- no server socket, no network."""
from harness import server
from harness import hooks as _hooks


def _raise(exc):
    def _f(*_a, **_k):
        raise exc
    return _f


def test_finalize_turn_swallows_transcript_serialization_error(monkeypatch):
    class _Sessions:
        active = "sess-1"

    class _Pilot:
        def export_transcript_data(self):
            raise RuntimeError("unserializable transcript object")

    class _Cfg:
        state_dir = None

    monkeypatch.setattr(server, "_sessions", _Sessions())
    monkeypatch.setattr(server, "_pilot", _Pilot())
    monkeypatch.setattr(server, "_cfg", _Cfg())
    monkeypatch.setattr(_hooks, "run_hooks", lambda *a, **k: None)
    # A save-path that should never be reached because export blows up first; if it
    # is reached, a failure would still have to be swallowed.
    monkeypatch.setattr(server, "save_transcript", _raise(AssertionError("unreachable")))

    # Must return normally despite the raising export_transcript_data.
    server._finalize_turn({"trigger": "chat"})


def test_finalize_turn_swallows_posthook_error(monkeypatch):
    class _Sessions:
        active = None  # no transcript persist; isolate the hook failure

    monkeypatch.setattr(server, "_sessions", _Sessions())
    monkeypatch.setattr(_hooks, "run_hooks", _raise(RuntimeError("bad hook")))

    server._finalize_turn({"trigger": "chat"})


def test_finalize_turn_persists_when_all_healthy(monkeypatch):
    calls = {}

    class _Sessions:
        active = "sess-1"

    class _Pilot:
        def export_transcript_data(self):
            return {"messages": []}

    class _Cfg:
        state_dir = "/tmp"

    monkeypatch.setattr(server, "_sessions", _Sessions())
    monkeypatch.setattr(server, "_pilot", _Pilot())
    monkeypatch.setattr(server, "_cfg", _Cfg())
    monkeypatch.setattr(_hooks, "run_hooks", lambda *a, **k: calls.setdefault("hook", True))
    monkeypatch.setattr(server, "save_transcript",
                        lambda *a, **k: calls.setdefault("saved", True))

    server._finalize_turn({"trigger": "chat"})
    assert calls == {"hook": True, "saved": True}
