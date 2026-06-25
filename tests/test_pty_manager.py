"""Tests for the built-in terminal PTY manager (stdlib-only)."""
import time

from harness.pty_manager import PtyManager


def test_pty_create_write_read_kill():
    m = PtyManager()
    s = m.create(cwd="/tmp", cols=80, rows=24)
    assert s.id
    assert s.alive()
    time.sleep(0.5)  # shell init
    s.write("echo PTY_TEST_$((6*7))\n")
    time.sleep(0.7)
    data, off = s.read_since(0)
    out = data.decode("utf-8", "replace")
    assert "PTY_TEST_42" in out
    # incremental read returns only new bytes
    s.write("printf done\n")
    time.sleep(0.4)
    data2, off2 = s.read_since(off)
    assert off2 >= off
    m.kill(s.id)
    time.sleep(0.2)
    assert not s.alive()
    assert m.get(s.id) is None


def test_pty_resize_does_not_crash():
    m = PtyManager()
    s = m.create(cwd="/tmp")
    s.resize(40, 120)
    assert s.cols == 120 and s.rows == 40
    m.kill(s.id)


def test_pty_get_missing_returns_none():
    m = PtyManager()
    assert m.get("nonexistent") is None
