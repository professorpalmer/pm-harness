"""Jobs-poll resilience regression: a transient SQLite 'database is locked'
(e.g. a lingering second backend during a relaunch) must not 500 the /api/jobs
poll and disconnect the UI. _jobs_snapshot retries briefly, then serves the last
known snapshot. Hermetic -- no server socket, no real store."""
import sqlite3
from harness import server


class _State:
    def __init__(self, jobs=None, exc=None):
        self._jobs = jobs or []
        self._exc = exc

    def list_jobs(self):
        if self._exc is not None:
            raise self._exc
        return self._jobs


class _Session:
    def __init__(self, state):
        self._state = state

    def state(self):
        return self._state


def test_jobs_snapshot_returns_and_caches(monkeypatch):
    monkeypatch.setattr(server, "_last_jobs_snapshot", [])
    monkeypatch.setattr(server, "_session", _Session(_State(jobs=[{"id": "a"}])))
    assert server._jobs_snapshot() == [{"id": "a"}]
    assert server._last_jobs_snapshot == [{"id": "a"}]


def test_jobs_snapshot_falls_back_to_last_known_on_locked(monkeypatch):
    monkeypatch.setattr(server, "_last_jobs_snapshot", [{"id": "cached"}])
    monkeypatch.setattr(
        server, "_session",
        _Session(_State(exc=sqlite3.OperationalError("database is locked"))))
    # Must not raise; a locked DB serves the last-known snapshot instead of 500ing.
    assert server._jobs_snapshot() == [{"id": "cached"}]


def test_jobs_snapshot_other_error_also_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(server, "_last_jobs_snapshot", [{"id": "prev"}])
    monkeypatch.setattr(
        server, "_session", _Session(_State(exc=RuntimeError("unexpected"))))
    assert server._jobs_snapshot() == [{"id": "prev"}]
