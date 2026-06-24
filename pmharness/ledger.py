from __future__ import annotations

"""Append-only SQLite ledger of every scored attempt. Numbers-only, local,
reproducible -- the same philosophy as Puppetmaster's savings ledger. This is
the durable record the 'ideal harness model' research is built on.
"""

import sqlite3
import time
from pathlib import Path

from .scoring import Score


SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    ts           REAL NOT NULL,
    model        TEXT NOT NULL,
    task_id      TEXT NOT NULL,
    expected     TEXT NOT NULL,
    got          TEXT,
    json_valid   INTEGER NOT NULL,
    schema_valid INTEGER NOT NULL,
    action_correct INTEGER NOT NULL,
    executed_ok  INTEGER,
    score        REAL NOT NULL,
    tokens_in    INTEGER NOT NULL,
    tokens_out   INTEGER NOT NULL,
    latency_ms   REAL NOT NULL,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_run   ON attempts(run_id);
CREATE INDEX IF NOT EXISTS idx_attempts_model ON attempts(model);
"""


class Ledger:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record(self, run_id, score):
        self.conn.execute(
            "INSERT INTO attempts "
            "(run_id, ts, model, task_id, expected, got, json_valid, "
            "schema_valid, action_correct, executed_ok, score, "
            "tokens_in, tokens_out, latency_ms, error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, time.time(), score.model, score.task_id,
                score.expected_action, score.got_action,
                int(score.json_valid), int(score.schema_valid),
                int(score.action_correct),
                None if score.executed_ok is None else int(score.executed_ok),
                score.score, score.tokens_in, score.tokens_out,
                score.latency_ms, score.error,
            ),
        )
        self.conn.commit()

    def summary(self, run_id):
        cur = self.conn.execute(
            "SELECT model, COUNT(*) AS n, "
            "ROUND(AVG(json_valid)*100,1) AS json_pct, "
            "ROUND(AVG(schema_valid)*100,1) AS schema_pct, "
            "ROUND(AVG(action_correct)*100,1) AS action_pct, "
            "ROUND(AVG(score)*100,1) AS avg_score, "
            "SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, "
            "ROUND(AVG(latency_ms),0) AS avg_latency "
            "FROM attempts WHERE run_id=? GROUP BY model ORDER BY avg_score DESC",
            (run_id,),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self):
        self.conn.close()


TRAJ_SCHEMA = """
CREATE TABLE IF NOT EXISTS trajectories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    ts           REAL NOT NULL,
    model        TEXT NOT NULL,
    episode_id   TEXT NOT NULL,
    terminated   INTEGER NOT NULL,
    correct_action INTEGER NOT NULL,
    efficient    INTEGER NOT NULL,
    all_valid    INTEGER NOT NULL,
    grounded     INTEGER,
    swarms_run   INTEGER NOT NULL,
    turns        INTEGER NOT NULL,
    score        REAL NOT NULL,
    expect_terminal TEXT,
    got_terminal TEXT,
    tokens_out   INTEGER NOT NULL,
    latency_ms   REAL NOT NULL,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_traj_run ON trajectories(run_id);
"""


class TrajectoryLedger:
    def __init__(self, path):
        import sqlite3
        from pathlib import Path
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(TRAJ_SCHEMA)
        self.conn.commit()

    def record(self, run_id, ts):
        import time
        self.conn.execute(
            "INSERT INTO trajectories (run_id, ts, model, episode_id, terminated, "
            "correct_action, efficient, all_valid, grounded, swarms_run, turns, "
            "score, expect_terminal, got_terminal, tokens_out, latency_ms, error) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, time.time(), ts.model, ts.episode_id, int(ts.terminated),
             int(ts.correct_action), int(ts.efficient), int(ts.all_valid),
             None if ts.grounded is None else int(ts.grounded),
             ts.swarms_run, ts.turns, ts.score, ts.expect_terminal,
             ts.got_terminal, ts.total_tokens_out, ts.total_latency_ms, ts.error),
        )
        self.conn.commit()

    def summary(self, run_id):
        cur = self.conn.execute(
            "SELECT model, COUNT(*) n, "
            "ROUND(AVG(terminated)*100,1) term_pct, "
            "ROUND(AVG(correct_action)*100,1) action_pct, "
            "ROUND(AVG(efficient)*100,1) eff_pct, "
            "ROUND(AVG(all_valid)*100,1) valid_pct, "
            "ROUND(AVG(score)*100,1) avg_score, "
            "SUM(tokens_out) tout, ROUND(AVG(latency_ms),0) lat "
            "FROM trajectories WHERE run_id=? GROUP BY model ORDER BY avg_score DESC",
            (run_id,))
        cols=[c[0] for c in cur.description]
        return [dict(zip(cols,row)) for row in cur.fetchall()]

    def close(self):
        self.conn.close()
