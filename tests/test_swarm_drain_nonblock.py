"""drain_swarm_results must NOT block on the _busy lock. It's called from an HTTP
handler (the frontend swarm-results poll); a blocking acquire there hangs the
server thread whenever a turn holds the lock -- the 'swarm running forever / app
hung' symptom. It must return immediately (draining nothing) when busy, and the
queued results survive for the next poll."""
import tempfile
import threading

from harness.config import HarnessConfig
from harness.conversation import ConversationalSession


def _session():
    cfg = HarnessConfig(driver="stub-oracle-v2", state_dir=tempfile.mkdtemp())
    return ConversationalSession(cfg)


def test_drain_does_not_block_when_busy():
    s = _session()
    # Simulate an in-flight turn holding the lock.
    s._busy.acquire(blocking=False)
    try:
        done = threading.Event()

        def call_drain():
            list(s.drain_swarm_results())  # must return immediately, not block
            done.set()

        t = threading.Thread(target=call_drain, daemon=True)
        t.start()
        # If drain blocks on the held lock, this times out (the bug).
        assert done.wait(timeout=2.0), "drain_swarm_results blocked while _busy was held"
    finally:
        s._busy.release()


def test_drain_works_when_free():
    s = _session()
    # Lock free -> drain runs (yields nothing since the queue is empty, no error).
    out = list(s.drain_swarm_results())
    assert out == []
