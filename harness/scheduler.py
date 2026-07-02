from __future__ import annotations

"""Scheduler: the daemon that drives due schedules through Fully-Auto mode.

WHY this shape: the scheduler must DRIVE the existing unattended entry point
(ConversationalSession.run_auto), never reimplement autonomy or ceilings. Each
due schedule becomes one bounded run_auto session governed by an AutoBudget
built from the schedule's ceilings (0 -> governor default). We consume the
event generator to the terminal 'auto_halt', extract the final reason and the
last governor snapshot (cycles/tokens/swarms), persist a run row, update the
schedule's last_run, and hand a concise summary to a pluggable Notifier.

Two design rules make this safe and testable:
  1. Isolation: every schedule's run is wrapped in try/except so one failing
     job never kills the tick or the daemon. Failures are recorded as
     status='error' with the exception text.
  2. Injection seams: session_factory and budget_factory exist ONLY so tests
     can substitute deterministic stubs. In production they default to the real
     ConversationalSession and AutoBudget -- no network or Puppetmaster is
     touched here beyond what run_auto itself does.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, List, Optional

from .schedule_core import CronExpr, Schedule
from .schedule_store import ScheduleStore


class Notifier(ABC):
    """Delivery seam for run summaries. Pluggable so a messaging gateway can be
    injected later without editing the daemon."""

    @abstractmethod
    def notify(self, schedule: Schedule, run: dict) -> None:  # pragma: no cover
        raise NotImplementedError


class LogNotifier(Notifier):
    """Default notifier: prints a concise plain-text summary (no emoji)."""

    def notify(self, schedule: Schedule, run: dict) -> None:
        print(
            "schedule {id} ({name}): {status}"
            " reason={reason} cycles={cycles}"
            " tokens={tokens} swarms={swarms}".format(
                id=schedule.id,
                name=schedule.name,
                status=run.get("status", ""),
                reason=run.get("halt_reason", ""),
                cycles=run.get("cycles", 0),
                tokens=run.get("tokens_used", 0),
                swarms=run.get("swarms_used", 0),
            )
        )


def _default_budget_factory(schedule: Schedule):
    """Build an AutoBudget from the schedule ceilings, filling 0s with the
    governor's from_env defaults so a partially-specified schedule is still
    fully bounded."""
    from .autobudget import AutoBudget

    base = AutoBudget.from_env()
    return AutoBudget(
        max_tokens=schedule.max_tokens or base.max_tokens,
        max_seconds=schedule.max_seconds or base.max_seconds,
        max_swarms=schedule.max_swarms or base.max_swarms,
        max_idle_steps=base.max_idle_steps,
        killswitch_path=base.killswitch_path,
    )


def _default_session_factory(schedule: Schedule):
    """Build a real ConversationalSession configured for this schedule."""
    from .config import HarnessConfig
    from .conversation import ConversationalSession

    cfg = HarnessConfig.from_env()
    if schedule.repo:
        cfg.repo = schedule.repo
    if schedule.swarm_adapter:
        cfg.swarm_adapter = schedule.swarm_adapter
    if schedule.driver:
        cfg.driver = schedule.driver
    return ConversationalSession(cfg)


def _is_due(schedule: Schedule, now: datetime) -> bool:
    """A schedule is due if it fires exactly at this minute, or if its next fire
    since the last run is already in the past (a missed tick catch-up)."""
    if not schedule.enabled:
        return False
    try:
        cron = CronExpr.parse(schedule.cron)
    except ValueError:
        return False
    if cron.matches(now):
        return True
    if schedule.last_run_at:
        anchor = datetime.fromtimestamp(schedule.last_run_at)
        try:
            nxt = cron.next_after(anchor)
        except ValueError:
            return False
        return nxt <= now
    return False


def run_due(
    store: ScheduleStore,
    now: Optional[datetime] = None,
    *,
    notifier: Optional[Notifier] = None,
    session_factory: Optional[Callable[[Schedule], object]] = None,
    budget_factory: Optional[Callable[[Schedule], object]] = None,
) -> List[dict]:
    """Run every due-and-enabled schedule ONCE. Returns the list of run dicts.

    Each due schedule is driven through run_auto under a per-schedule budget.
    Failures are isolated: one schedule raising never aborts the others.
    """
    now = now or datetime.now()
    notifier = notifier or LogNotifier()
    session_factory = session_factory or _default_session_factory
    budget_factory = budget_factory or _default_budget_factory

    results: List[dict] = []
    for schedule in store.list(enabled_only=True):
        if not _is_due(schedule, now):
            continue
        results.append(
            _run_one(schedule, store, notifier, session_factory, budget_factory)
        )
    return results


def run_one_now(
    store: ScheduleStore,
    schedule_id: str,
    *,
    notifier: Optional[Notifier] = None,
    session_factory: Optional[Callable[[Schedule], object]] = None,
    budget_factory: Optional[Callable[[Schedule], object]] = None,
) -> Optional[dict]:
    """Run a single named schedule immediately, bypassing the due check (used by
    the `run-now` CLI). Returns the run dict, or None if the id is unknown."""
    schedule = store.get(schedule_id)
    if schedule is None:
        return None
    notifier = notifier or LogNotifier()
    session_factory = session_factory or _default_session_factory
    budget_factory = budget_factory or _default_budget_factory
    return _run_one(schedule, store, notifier, session_factory, budget_factory)


def _run_one(
    schedule: Schedule,
    store: ScheduleStore,
    notifier: Notifier,
    session_factory: Callable[[Schedule], object],
    budget_factory: Callable[[Schedule], object],
) -> dict:
    started_at = time.time()
    status = "ok"
    halt_reason = ""
    cycles = 0
    tokens_used = 0
    swarms_used = 0
    try:
        session = session_factory(schedule)
        budget = budget_factory(schedule)
        last_snapshot: dict = {}
        for ev in session.run_auto(schedule.objective, budget):
            data = getattr(ev, "data", None) or {}
            if getattr(ev, "kind", "") == "auto_status":
                snap = data.get("snapshot") or {}
                if snap:
                    last_snapshot = snap
                if "cycle" in data:
                    cycles = int(data["cycle"])
            elif getattr(ev, "kind", "") == "auto_halt":
                halt_reason = str(data.get("reason", ""))
                snap = data.get("snapshot") or {}
                if snap:
                    last_snapshot = snap
        tokens_used = int(last_snapshot.get("tokens_used", 0) or 0)
        swarms_used = int(last_snapshot.get("swarms_used", 0) or 0)
    except Exception as exc:  # isolation: never let one job kill the loop
        status = "error"
        halt_reason = f"{type(exc).__name__}: {exc}"

    ended_at = time.time()
    run = {
        "schedule_id": schedule.id,
        "started_at": started_at,
        "ended_at": ended_at,
        "status": status,
        "halt_reason": halt_reason,
        "cycles": cycles,
        "tokens_used": tokens_used,
        "swarms_used": swarms_used,
    }
    store.record_run(**run)
    store.update_last_run(schedule.id, status, ended_at)
    try:
        notifier.notify(schedule, run)
    except Exception:  # a broken notifier must not break the run record
        pass
    return run


class SchedulerDaemon:
    """Long-running loop: on each tick, run all due schedules, then sleep.

    Resilient by construction: an exception in a single tick is logged and the
    loop continues (a transient store or session error must not take the daemon
    down overnight). Ctrl-C exits cleanly.
    """

    def __init__(
        self,
        store: ScheduleStore,
        *,
        notifier: Optional[Notifier] = None,
        session_factory: Optional[Callable[[Schedule], object]] = None,
        budget_factory: Optional[Callable[[Schedule], object]] = None,
    ) -> None:
        self.store = store
        self.notifier = notifier or LogNotifier()
        self.session_factory = session_factory
        self.budget_factory = budget_factory
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def tick(self, now: Optional[datetime] = None) -> List[dict]:
        return run_due(
            self.store,
            now,
            notifier=self.notifier,
            session_factory=self.session_factory,
            budget_factory=self.budget_factory,
        )

    def serve(self, tick_seconds: int = 30) -> None:
        print(f"scheduler daemon started (tick={tick_seconds}s); Ctrl-C to stop")
        try:
            while not self._stop:
                try:
                    runs = self.tick()
                    if runs:
                        print(f"tick: ran {len(runs)} schedule(s)")
                except Exception as exc:  # keep the daemon alive across ticks
                    print(f"tick error (continuing): {type(exc).__name__}: {exc}")
                time.sleep(max(1, int(tick_seconds)))
        except KeyboardInterrupt:
            print("scheduler daemon stopped")
