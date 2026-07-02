"""run_due proofs with injected fakes: exactly the due schedules run, runs are
recorded with the right snapshot fields, disabled ones skip, a raising factory
is isolated as status='error', and the notifier fires once per run.

No real Puppetmaster, no network -- session_factory/budget_factory are stubs,
mirroring the _fake_result / _NeverDonePilot injection style of test_auto.py.
"""
from datetime import datetime

from harness.schedule_core import Schedule
from harness.schedule_store import ScheduleStore
from harness.scheduler import Notifier, run_due


class _Event:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data


class _FakeSession:
    """Yields two auto_status events then a terminal auto_halt, like run_auto."""

    def __init__(self, reason, cycles, tokens, swarms):
        self._reason = reason
        self._cycles = cycles
        self._tokens = tokens
        self._swarms = swarms

    def run_auto(self, objective, budget=None, *, require_codegraph=True):
        yield _Event("auto_status", {"cycle": 1, "snapshot": {
            "tokens_used": 1, "swarms_used": 0}})
        yield _Event("auto_status", {"cycle": self._cycles, "snapshot": {
            "tokens_used": self._tokens, "swarms_used": self._swarms}})
        yield _Event("auto_halt", {"reason": self._reason, "snapshot": {
            "tokens_used": self._tokens, "swarms_used": self._swarms}})


class _CountingNotifier(Notifier):
    def __init__(self):
        self.calls = []

    def notify(self, schedule, run):
        self.calls.append((schedule.id, run))


class _FakeBudget:
    pass


def _session_factory(reason="done", cycles=2, tokens=42, swarms=3):
    return lambda sched: _FakeSession(reason, cycles, tokens, swarms)


def _budget_factory(sched):
    return _FakeBudget()


def _store(tmp_path):
    return ScheduleStore(str(tmp_path / "s.sqlite"))


def _now():
    # A minute that "* * * * *" always matches.
    return datetime(2024, 1, 1, 12, 0)


def test_only_due_enabled_run(tmp_path):
    store = _store(tmp_path)
    due = store.add(Schedule(id="", name="due", objective="o", cron="* * * * *"))
    # A never-firing schedule (Feb 30 does not exist) is not due.
    not_due = store.add(Schedule(id="", name="nd", objective="o", cron="0 0 30 2 *"))
    notifier = _CountingNotifier()

    runs = run_due(store, _now(), notifier=notifier,
                   session_factory=_session_factory(),
                   budget_factory=_budget_factory)

    assert len(runs) == 1
    assert runs[0]["schedule_id"] == due.id
    assert len(store.list_runs(not_due.id)) == 0


def test_run_records_snapshot_fields(tmp_path):
    store = _store(tmp_path)
    s = store.add(Schedule(id="", name="x", objective="o", cron="* * * * *"))
    notifier = _CountingNotifier()

    run_due(store, _now(), notifier=notifier,
            session_factory=_session_factory(reason="objective met",
                                             cycles=5, tokens=999, swarms=7),
            budget_factory=_budget_factory)

    recorded = store.list_runs(s.id)
    assert len(recorded) == 1
    r = recorded[0]
    assert r["status"] == "ok"
    assert r["halt_reason"] == "objective met"
    assert r["cycles"] == 5
    assert r["tokens_used"] == 999
    assert r["swarms_used"] == 7
    # last_run updated on the schedule row.
    assert store.get(s.id).last_status == "ok"
    assert store.get(s.id).last_run_at > 0


def test_disabled_skipped(tmp_path):
    store = _store(tmp_path)
    s = store.add(Schedule(id="", name="off", objective="o",
                           cron="* * * * *", enabled=False))
    runs = run_due(store, _now(), notifier=_CountingNotifier(),
                   session_factory=_session_factory(),
                   budget_factory=_budget_factory)
    assert runs == []
    assert store.list_runs(s.id) == []


def test_raising_factory_isolated_as_error(tmp_path):
    store = _store(tmp_path)
    bad = store.add(Schedule(id="", name="bad", objective="o", cron="* * * * *"))
    good = store.add(Schedule(id="", name="good", objective="o", cron="* * * * *"))
    notifier = _CountingNotifier()

    def factory(sched):
        if sched.id == bad.id:
            raise RuntimeError("kaboom")
        return _FakeSession("done", 1, 5, 0)

    runs = run_due(store, _now(), notifier=notifier,
                   session_factory=factory, budget_factory=_budget_factory)

    assert len(runs) == 2  # bad one did not abort the good one
    bad_run = store.list_runs(bad.id)[0]
    assert bad_run["status"] == "error"
    assert "kaboom" in bad_run["halt_reason"]
    good_run = store.list_runs(good.id)[0]
    assert good_run["status"] == "ok"


def test_notifier_called_once_per_run(tmp_path):
    store = _store(tmp_path)
    store.add(Schedule(id="", name="a", objective="o", cron="* * * * *"))
    store.add(Schedule(id="", name="b", objective="o", cron="* * * * *"))
    notifier = _CountingNotifier()

    run_due(store, _now(), notifier=notifier,
            session_factory=_session_factory(),
            budget_factory=_budget_factory)

    assert len(notifier.calls) == 2
