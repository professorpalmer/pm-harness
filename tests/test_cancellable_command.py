"""Tests for the cancellable command runner. The gap it closes: subprocess.run
blocks the thread uninterruptibly, so a user Stop could not kill a long/unbounded
command. run_cancellable polls a cancel event and kills the whole process group.
"""
import threading
import time

import pytest

from harness.command_policy import run_cancellable


def test_normal_completion():
    out, code, status = run_cancellable("echo hello", timeout=10)
    assert "hello" in out
    assert code == 0
    assert status == "ok"


def test_nonzero_exit():
    out, code, status = run_cancellable("exit 3", timeout=10)
    assert code == 3
    assert status == "ok"


def test_cancel_kills_promptly():
    ev = threading.Event()
    threading.Thread(target=lambda: (time.sleep(0.3), ev.set())).start()
    t0 = time.time()
    out, code, status = run_cancellable("sleep 30", timeout=None, cancel_event=ev)
    elapsed = time.time() - t0
    assert status == "cancelled"
    assert code == 130
    assert elapsed < 5, f"cancel took {elapsed}s -- should be sub-second"
    assert "interrupted by user" in out


def test_timeout_kills():
    t0 = time.time()
    out, code, status = run_cancellable("sleep 30", timeout=1)
    elapsed = time.time() - t0
    assert status == "timeout"
    assert elapsed < 5
    assert "TimeoutExpired" in out


def test_process_group_kill_no_orphans():
    # children spawned by the shell must also die (group kill, not just the shell).
    # The kill is SIGTERM -> grace -> SIGKILL, and the OS reaps asynchronously, so
    # POLL for the orphan count to reach 0 rather than checking once after a fixed
    # sleep (that fixed-delay check raced on slow/loaded CI runners -- the kill was
    # correct, the assertion was just too eager). Use a unique marker so a
    # concurrent test's "sleep" can never be miscounted as our orphan.
    import subprocess as sp
    marker = "orphan_probe_4193"
    ev = threading.Event()
    threading.Thread(target=lambda: (time.sleep(0.3), ev.set())).start()
    run_cancellable(
        f"sleep 23 # {marker}\n sleep 23 # {marker}\n wait",
        timeout=None, cancel_event=ev,
    )
    deadline = time.time() + 8.0
    remaining = None
    while time.time() < deadline:
        n = sp.run(f"pgrep -f {marker} | wc -l", shell=True, capture_output=True, text=True)
        remaining = n.stdout.strip()
        if remaining == "0":
            break
        time.sleep(0.2)
    assert remaining == "0", "child processes were orphaned, not group-killed"


def test_bad_command_does_not_raise():
    out, code, status = run_cancellable("this_command_does_not_exist_xyz", timeout=5)
    # shell returns 127 for not-found; never raises
    assert code != 0
    assert status in ("ok", "error")
