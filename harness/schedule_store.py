from __future__ import annotations

"""ScheduleStore: durable sqlite persistence for schedules and their run log.

WHY sqlite (not JSON like memory_store): schedules accumulate a run history and
are queried by predicates (enabled-only, runs-for-a-schedule, most-recent-N).
A relational store gives us cheap indexed reads and atomic row updates without
rewriting a whole file on every tick. We follow the exact house pattern from
memory_store.py / command_store.py: a thin class wrapping a sqlite path, tables
created idempotently in __init__, simple typed methods, and a stable default
path under the harness state dir with an explicit-path override for tests.
"""

import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Optional

from .schedule_core import SCHEDULE_FIELDS, Schedule

DEFAULT_DB_PATH = Path(os.path.expanduser("~/.harness/schedules.sqlite"))


class ScheduleStore:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                objective TEXT NOT NULL,
                cron TEXT NOT NULL,
                repo TEXT NOT NULL DEFAULT '',
                swarm_adapter TEXT NOT NULL DEFAULT 'demo',
                driver TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                max_tokens INTEGER NOT NULL DEFAULT 0,
                max_seconds INTEGER NOT NULL DEFAULT 0,
                max_swarms INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT 0,
                last_run_at REAL NOT NULL DEFAULT 0,
                last_status TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedule_runs (
                id TEXT PRIMARY KEY,
                schedule_id TEXT NOT NULL,
                started_at REAL NOT NULL,
                ended_at REAL NOT NULL,
                status TEXT NOT NULL,
                halt_reason TEXT NOT NULL DEFAULT '',
                cycles INTEGER NOT NULL DEFAULT 0,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                swarms_used INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_sched "
            "ON schedule_runs(schedule_id, started_at)"
        )
        self._conn.commit()

    def add(self, schedule: Schedule) -> Schedule:
        """Insert a schedule. If id/created_at are unset, they are generated."""
        if not schedule.id:
            schedule.id = uuid.uuid4().hex[:8]
        if not schedule.created_at:
            schedule.created_at = time.time()
        row = schedule.to_row()
        cols = ",".join(SCHEDULE_FIELDS)
        placeholders = ",".join("?" for _ in SCHEDULE_FIELDS)
        self._conn.execute(
            f"INSERT INTO schedules ({cols}) VALUES ({placeholders})",
            [row[f] for f in SCHEDULE_FIELDS],
        )
        self._conn.commit()
        return schedule

    def list(self, enabled_only: bool = False) -> List[Schedule]:
        sql = "SELECT * FROM schedules"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at ASC"
        rows = self._conn.execute(sql).fetchall()
        return [Schedule.from_row(dict(r)) for r in rows]

    def get(self, schedule_id: str) -> Optional[Schedule]:
        row = self._conn.execute(
            "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        return Schedule.from_row(dict(row)) if row else None

    def remove(self, schedule_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM schedules WHERE id = ?", (schedule_id,)
        )
        self._conn.execute(
            "DELETE FROM schedule_runs WHERE schedule_id = ?", (schedule_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def set_enabled(self, schedule_id: str, enabled: bool) -> bool:
        cur = self._conn.execute(
            "UPDATE schedules SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, schedule_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def update_last_run(self, schedule_id: str, status: str, ts: float) -> bool:
        cur = self._conn.execute(
            "UPDATE schedules SET last_status = ?, last_run_at = ? WHERE id = ?",
            (status, ts, schedule_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def record_run(
        self,
        schedule_id: str,
        started_at: float,
        ended_at: float,
        status: str,
        halt_reason: str = "",
        cycles: int = 0,
        tokens_used: int = 0,
        swarms_used: int = 0,
    ) -> str:
        run_id = uuid.uuid4().hex[:8]
        self._conn.execute(
            """
            INSERT INTO schedule_runs
                (id, schedule_id, started_at, ended_at, status,
                 halt_reason, cycles, tokens_used, swarms_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, schedule_id, started_at, ended_at, status,
             halt_reason, int(cycles), int(tokens_used), int(swarms_used)),
        )
        self._conn.commit()
        return run_id

    def list_runs(self, schedule_id: str, limit: int = 50) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM schedule_runs WHERE schedule_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (schedule_id, int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
