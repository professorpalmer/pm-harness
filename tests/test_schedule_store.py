"""ScheduleStore proofs: CRUD, filters, id autogen, run log, persistence."""
import time

from harness.schedule_core import Schedule
from harness.schedule_store import ScheduleStore


def _mk(name="n", cron="* * * * *", enabled=True):
    return Schedule(id="", name=name, objective="obj", cron=cron, enabled=enabled)


def test_add_autogen_id_and_created_at(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    s = store.add(_mk())
    assert s.id and len(s.id) == 8
    assert s.created_at > 0


def test_add_get_list(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk("a"))
    b = store.add(_mk("b"))
    assert {x.id for x in store.list()} == {a.id, b.id}
    got = store.get(a.id)
    assert got is not None and got.name == "a"
    assert store.get("nope") is None


def test_enabled_only_filter(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk("on", enabled=True))
    b = store.add(_mk("off", enabled=False))
    ids = {x.id for x in store.list(enabled_only=True)}
    assert a.id in ids and b.id not in ids


def test_remove(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk())
    assert store.remove(a.id) is True
    assert store.get(a.id) is None
    assert store.remove(a.id) is False


def test_set_enabled(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk(enabled=True))
    assert store.set_enabled(a.id, False) is True
    assert store.get(a.id).enabled is False
    assert store.set_enabled("nope", True) is False


def test_update_last_run(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk())
    ts = time.time()
    assert store.update_last_run(a.id, "ok", ts) is True
    got = store.get(a.id)
    assert got.last_status == "ok"
    assert abs(got.last_run_at - ts) < 1.0


def test_record_and_list_runs(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk())
    store.record_run(a.id, 1.0, 2.0, "ok", halt_reason="done",
                     cycles=3, tokens_used=100, swarms_used=2)
    store.record_run(a.id, 3.0, 4.0, "error", halt_reason="boom")
    runs = store.list_runs(a.id)
    assert len(runs) == 2
    # Most recent first.
    assert runs[0]["status"] == "error"
    assert runs[1]["cycles"] == 3
    assert runs[1]["tokens_used"] == 100
    assert runs[1]["swarms_used"] == 2


def test_persistence_across_reopen(tmp_path):
    path = str(tmp_path / "s.sqlite")
    store = ScheduleStore(path)
    a = store.add(_mk("persist"))
    store.record_run(a.id, 1.0, 2.0, "ok")
    store.close()

    reopened = ScheduleStore(path)
    got = reopened.get(a.id)
    assert got is not None and got.name == "persist"
    assert len(reopened.list_runs(a.id)) == 1


def test_remove_purges_runs(tmp_path):
    store = ScheduleStore(str(tmp_path / "s.sqlite"))
    a = store.add(_mk())
    store.record_run(a.id, 1.0, 2.0, "ok")
    store.remove(a.id)
    assert store.list_runs(a.id) == []
