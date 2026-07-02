from __future__ import annotations

"""schedule CLI: manage and run scheduled unattended objectives.

  harness schedule add --name nightly --cron "0 2 * * *" --objective "..."
  harness schedule list
  harness schedule remove <id>
  harness schedule enable <id>
  harness schedule disable <id>
  harness schedule run-now <id>
  harness schedule daemon [--tick 30]

This is the harness-coupled front end for the pure schedule_core plus the
ScheduleStore and scheduler daemon. It mirrors the manual-dispatch + ANSI _c
style of cli.py. Cron expressions are validated at `add` time (parsed and the
next three fire times printed); an invalid expression exits 1.
"""

import argparse
import sys
from datetime import datetime

from .schedule_core import CronExpr, Schedule
from .schedule_store import ScheduleStore


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else s


def _next_fires(cron: CronExpr, count: int = 3) -> list:
    out = []
    cur = datetime.now()
    for _ in range(count):
        cur = cron.next_after(cur)
        out.append(cur)
    return out


def _cmd_add(args) -> int:
    store = ScheduleStore(args.db)
    try:
        cron = CronExpr.parse(args.cron)
    except ValueError as exc:
        print(_c("31", f"invalid cron expression: {exc}"))
        return 1
    sched = Schedule(
        id="",
        name=args.name,
        objective=args.objective,
        cron=args.cron,
        repo=args.repo or "",
        swarm_adapter=args.swarm_adapter,
        driver=args.driver or "",
        max_tokens=args.max_tokens,
        max_seconds=args.max_seconds,
        max_swarms=args.max_swarms,
    )
    store.add(sched)
    print(_c("32", f"added schedule {sched.id} ({sched.name})"))
    print("next fires:")
    for dt in _next_fires(cron):
        print(f"  {dt.isoformat(sep=' ', timespec='minutes')}")
    return 0


def _cmd_list(args) -> int:
    store = ScheduleStore(args.db)
    scheds = store.list()
    if not scheds:
        print("no schedules")
        return 0
    for s in scheds:
        state = "enabled" if s.enabled else "disabled"
        last = s.last_status or "never"
        print(_c("36", f"{s.id}") + f"  {s.name}  [{state}]")
        print(f"    cron={s.cron!r} adapter={s.swarm_adapter} last={last}")
        print(f"    objective: {s.objective}")
    return 0


def _cmd_remove(args) -> int:
    store = ScheduleStore(args.db)
    if store.remove(args.id):
        print(_c("32", f"removed {args.id}"))
        return 0
    print(_c("31", f"no such schedule: {args.id}"))
    return 1


def _cmd_enable(args) -> int:
    store = ScheduleStore(args.db)
    if store.set_enabled(args.id, True):
        print(_c("32", f"enabled {args.id}"))
        return 0
    print(_c("31", f"no such schedule: {args.id}"))
    return 1


def _cmd_disable(args) -> int:
    store = ScheduleStore(args.db)
    if store.set_enabled(args.id, False):
        print(_c("32", f"disabled {args.id}"))
        return 0
    print(_c("31", f"no such schedule: {args.id}"))
    return 1


def _cmd_run_now(args) -> int:
    from .scheduler import run_one_now

    store = ScheduleStore(args.db)
    run = run_one_now(store, args.id)
    if run is None:
        print(_c("31", f"no such schedule: {args.id}"))
        return 1
    if run.get("status") == "error":
        print(_c("31", f"run errored: {run.get('halt_reason')}"))
        return 1
    print(_c("32", f"run complete: {run.get('halt_reason')}"))
    return 0


def _cmd_daemon(args) -> int:
    from .scheduler import SchedulerDaemon

    store = ScheduleStore(args.db)
    SchedulerDaemon(store).serve(tick_seconds=args.tick)
    return 0


def _run_schedule(argv) -> int:
    ap = argparse.ArgumentParser(
        prog="harness schedule",
        description="Manage scheduled unattended objectives.")
    ap.add_argument("--db", default=None, help="schedule store path (tests/override)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="add a schedule")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--cron", required=True, help="5-field cron expression")
    p_add.add_argument("--objective", required=True)
    p_add.add_argument("--repo", default=None)
    p_add.add_argument("--driver", default=None)
    p_add.add_argument("--swarm-adapter", dest="swarm_adapter", default="demo")
    p_add.add_argument("--max-tokens", dest="max_tokens", type=int, default=0)
    p_add.add_argument("--max-seconds", dest="max_seconds", type=int, default=0)
    p_add.add_argument("--max-swarms", dest="max_swarms", type=int, default=0)
    p_add.set_defaults(func=_cmd_add)

    p_list = sub.add_parser("list", help="list schedules")
    p_list.set_defaults(func=_cmd_list)

    p_rm = sub.add_parser("remove", help="remove a schedule")
    p_rm.add_argument("id")
    p_rm.set_defaults(func=_cmd_remove)

    p_en = sub.add_parser("enable", help="enable a schedule")
    p_en.add_argument("id")
    p_en.set_defaults(func=_cmd_enable)

    p_dis = sub.add_parser("disable", help="disable a schedule")
    p_dis.add_argument("id")
    p_dis.set_defaults(func=_cmd_disable)

    p_run = sub.add_parser("run-now", help="run one schedule immediately")
    p_run.add_argument("id")
    p_run.set_defaults(func=_cmd_run_now)

    p_dae = sub.add_parser("daemon", help="run the scheduler loop")
    p_dae.add_argument("--tick", type=int, default=30, help="seconds between ticks")
    p_dae.set_defaults(func=_cmd_daemon)

    args = ap.parse_args(argv)
    return args.func(args)
