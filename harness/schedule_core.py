from __future__ import annotations

"""Schedule core: the PURE, PM-free cron engine and Schedule record.

WHY this layer exists: the scheduler subsystem has two very different concerns.
One is time math (does a cron expression fire at this minute? when is the next
fire?) and the shape of a persisted schedule. That concern is deterministic,
has no side effects, and must be trivially unit-testable without touching
Puppetmaster, sqlite, or the network. The other concern -- actually driving a
run_auto session, persisting rows, notifying a gateway -- is coupled to the
harness. We keep those apart so the fiddly, edge-case-heavy cron math can be
proven hermetically and fast.

This module therefore imports ONLY the standard library (datetime, calendar,
dataclasses) and MUST NOT import harness.* or puppetmaster.* -- that invariant
is what keeps tests/test_schedule_core.py hermetic.

Cron semantics implemented (standard 5-field crontab):
    minute hour day-of-month month day-of-week
Supported per field: '*', comma lists (0,30), ranges (9-17), step on wildcard
(*/15) and step on range (0-30/10). Day-of-week accepts 0 and 7 as Sunday.
When BOTH day-of-month and day-of-week are restricted (neither is '*'), a
minute matches if EITHER the DOM or the DOW matches -- the well-known Vixie
cron OR-rule -- because that is what real crontabs expect.
"""

import calendar
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# Field bounds as (low, high) inclusive, in cron field order.
_FIELD_BOUNDS = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 7),    # day of week (0 and 7 both Sunday)
]
_FIELD_NAMES = ["minute", "hour", "day-of-month", "month", "day-of-week"]

# Cap next_after search so a pathological expression cannot loop forever.
# 4 years of minutes comfortably covers a Feb-29-only schedule.
_MAX_SEARCH_MINUTES = 4 * 366 * 24 * 60


def _parse_field(spec: str, low: int, high: int, name: str) -> frozenset:
    """Expand one cron field into the concrete set of ints it matches.

    Raises ValueError with a clear message on any malformed token.
    """
    spec = spec.strip()
    if not spec:
        raise ValueError(f"empty {name} field")
    values: set = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"empty term in {name} field: {spec!r}")
        step = 1
        if "/" in part:
            base, _, step_s = part.partition("/")
            try:
                step = int(step_s)
            except ValueError:
                raise ValueError(f"bad step {step_s!r} in {name} field")
            if step <= 0:
                raise ValueError(f"step must be positive in {name} field: {part!r}")
        else:
            base = part

        if base == "*":
            start, end = low, high
        elif "-" in base:
            lo_s, _, hi_s = base.partition("-")
            try:
                start, end = int(lo_s), int(hi_s)
            except ValueError:
                raise ValueError(f"bad range {base!r} in {name} field")
            if start > end:
                raise ValueError(f"inverted range {base!r} in {name} field")
        else:
            try:
                start = end = int(base)
            except ValueError:
                raise ValueError(f"bad value {base!r} in {name} field")

        if start < low or end > high:
            raise ValueError(
                f"{name} value out of range {low}-{high}: {base!r}")
        values.update(range(start, end + 1, step))

    if not values:
        raise ValueError(f"no values matched in {name} field: {spec!r}")
    return frozenset(values)


@dataclass(frozen=True)
class CronExpr:
    """A parsed, evaluatable 5-field cron expression.

    Fields are stored as concrete integer sets so matching is a cheap membership
    test. Day-of-week Sunday is normalized so both 0 and 7 are present.
    """

    minutes: frozenset
    hours: frozenset
    doms: frozenset
    months: frozenset
    dows: frozenset
    dom_restricted: bool
    dow_restricted: bool
    raw: str = ""

    @classmethod
    def parse(cls, expr: str) -> "CronExpr":
        if expr is None or not str(expr).strip():
            raise ValueError("empty cron expression")
        fields = str(expr).split()
        if len(fields) != 5:
            raise ValueError(
                f"cron expression must have 5 fields, got {len(fields)}: {expr!r}")
        sets = [
            _parse_field(fields[i], *_FIELD_BOUNDS[i], _FIELD_NAMES[i])
            for i in range(5)
        ]
        dows = set(sets[4])
        if 7 in dows:
            dows.add(0)
        if 0 in dows:
            dows.add(7)
        return cls(
            minutes=sets[0],
            hours=sets[1],
            doms=sets[2],
            months=sets[3],
            dows=frozenset(dows),
            dom_restricted=(fields[2].strip() != "*"),
            dow_restricted=(fields[4].strip() != "*"),
            raw=str(expr).strip(),
        )

    def _day_matches(self, dt: datetime) -> bool:
        # Python weekday(): Monday=0..Sunday=6. Cron dow: Sunday=0.
        cron_dow = (dt.weekday() + 1) % 7
        dom_ok = dt.day in self.doms
        dow_ok = cron_dow in self.dows
        if self.dom_restricted and self.dow_restricted:
            return dom_ok or dow_ok
        if self.dom_restricted:
            return dom_ok
        if self.dow_restricted:
            return dow_ok
        return True  # both wildcard

    def matches(self, dt: datetime) -> bool:
        """True if the given datetime (at minute resolution) fires this cron."""
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.month in self.months
            and self._day_matches(dt)
        )

    def next_after(self, dt: datetime) -> datetime:
        """Next fire time strictly after dt, at minute resolution.

        Search is capped at ~4 years; raise ValueError if nothing matches (which
        should only happen for an impossible date like Feb 30).
        """
        # Round up to the next whole minute strictly after dt.
        cur = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(_MAX_SEARCH_MINUTES):
            if self.matches(cur):
                return cur
            cur += timedelta(minutes=1)
        raise ValueError(
            f"no cron match within {_MAX_SEARCH_MINUTES // (24 * 60)} days "
            f"for {self.raw!r}")


# Ordered field names for row round-tripping and store schema.
SCHEDULE_FIELDS = [
    "id", "name", "objective", "cron", "repo", "swarm_adapter", "driver",
    "enabled", "max_tokens", "max_seconds", "max_swarms",
    "created_at", "last_run_at", "last_status",
]


@dataclass
class Schedule:
    """A durable scheduled objective. Zero for a ceiling means 'use the governor
    default' (resolved at run time, not stored as a magic number)."""

    id: str
    name: str
    objective: str
    cron: str
    repo: str = ""
    swarm_adapter: str = "demo"
    driver: str = ""
    enabled: bool = True
    max_tokens: int = 0
    max_seconds: int = 0
    max_swarms: int = 0
    created_at: float = 0.0
    last_run_at: float = 0.0
    last_status: str = ""

    def to_row(self) -> Dict[str, object]:
        """Flatten to a sqlite-friendly dict (bool -> int)."""
        d = asdict(self)
        d["enabled"] = 1 if self.enabled else 0
        return d

    @classmethod
    def from_row(cls, row: Dict[str, object]) -> "Schedule":
        """Rebuild from a sqlite row (int -> bool), ignoring extra columns."""
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            objective=str(row["objective"]),
            cron=str(row["cron"]),
            repo=str(row.get("repo") or ""),
            swarm_adapter=str(row.get("swarm_adapter") or "demo"),
            driver=str(row.get("driver") or ""),
            enabled=bool(row.get("enabled", 1)),
            max_tokens=int(row.get("max_tokens") or 0),
            max_seconds=int(row.get("max_seconds") or 0),
            max_swarms=int(row.get("max_swarms") or 0),
            created_at=float(row.get("created_at") or 0.0),
            last_run_at=float(row.get("last_run_at") or 0.0),
            last_status=str(row.get("last_status") or ""),
        )
