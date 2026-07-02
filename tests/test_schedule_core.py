"""Cron engine + Schedule record proofs -- pure, hermetic, no harness imports.

These lock down the fiddly cron edge cases (steps, ranges, DOM/DOW OR-rule,
Sunday-as-0-or-7, rollovers) so the daemon can trust the time math.
"""
from datetime import datetime

import pytest

from harness.schedule_core import CronExpr, Schedule


def _dt(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi)


def test_all_wildcards_matches_everything():
    c = CronExpr.parse("* * * * *")
    assert c.matches(_dt(2024, 1, 1, 0, 0))
    assert c.matches(_dt(2024, 6, 15, 13, 37))


def test_exact_minute_hour():
    c = CronExpr.parse("30 9 * * *")
    assert c.matches(_dt(2024, 3, 4, 9, 30))
    assert not c.matches(_dt(2024, 3, 4, 9, 31))
    assert not c.matches(_dt(2024, 3, 4, 10, 30))


def test_comma_list():
    c = CronExpr.parse("0,30 * * * *")
    assert c.matches(_dt(2024, 1, 1, 5, 0))
    assert c.matches(_dt(2024, 1, 1, 5, 30))
    assert not c.matches(_dt(2024, 1, 1, 5, 15))


def test_range():
    c = CronExpr.parse("0 9-17 * * *")
    assert c.matches(_dt(2024, 1, 1, 9, 0))
    assert c.matches(_dt(2024, 1, 1, 17, 0))
    assert not c.matches(_dt(2024, 1, 1, 8, 0))
    assert not c.matches(_dt(2024, 1, 1, 18, 0))


def test_step_on_wildcard():
    c = CronExpr.parse("*/15 * * * *")
    for m in (0, 15, 30, 45):
        assert c.matches(_dt(2024, 1, 1, 0, m))
    assert not c.matches(_dt(2024, 1, 1, 0, 10))


def test_step_on_range():
    c = CronExpr.parse("0-30/10 * * * *")
    for m in (0, 10, 20, 30):
        assert c.matches(_dt(2024, 1, 1, 0, m))
    assert not c.matches(_dt(2024, 1, 1, 0, 40))


def test_sunday_zero_and_seven_both_match():
    # 2024-01-07 is a Sunday.
    sun = _dt(2024, 1, 7, 12, 0)
    c0 = CronExpr.parse("0 12 * * 0")
    c7 = CronExpr.parse("0 12 * * 7")
    assert c0.matches(sun)
    assert c7.matches(sun)
    # Monday 2024-01-08 must not match a Sunday schedule.
    assert not c0.matches(_dt(2024, 1, 8, 12, 0))


def test_dom_dow_or_semantics():
    # Both DOM and DOW restricted -> match if EITHER. day 15 OR Monday(dow 1).
    c = CronExpr.parse("0 0 15 * 1")
    # 2024-01-15 is a Monday: both true.
    assert c.matches(_dt(2024, 1, 15, 0, 0))
    # 2024-01-08 is a Monday, not the 15th: still matches (DOW).
    assert c.matches(_dt(2024, 1, 8, 0, 0))
    # 2024-02-15 is a Thursday, not Monday: still matches (DOM).
    assert c.matches(_dt(2024, 2, 15, 0, 0))
    # 2024-01-09 is a Tuesday, not the 15th: no match.
    assert not c.matches(_dt(2024, 1, 9, 0, 0))


def test_dom_only_restricted():
    c = CronExpr.parse("0 0 1 * *")
    assert c.matches(_dt(2024, 5, 1, 0, 0))
    assert not c.matches(_dt(2024, 5, 2, 0, 0))


@pytest.mark.parametrize("bad", [
    "",
    "* * * *",            # 4 fields
    "* * * * * *",        # 6 fields
    "60 * * * *",         # minute out of range
    "* 24 * * *",         # hour out of range
    "* * 0 * *",          # dom below range
    "* * * 13 *",         # month out of range
    "* * * * 8",          # dow out of range
    "5-1 * * * *",        # inverted range
    "*/0 * * * *",        # zero step
    "*/x * * * *",        # bad step
    "a * * * *",          # bad value
    "1,,2 * * * *",       # empty term
])
def test_malformed_raises(bad):
    with pytest.raises(ValueError):
        CronExpr.parse(bad)


def test_next_after_hour_rollover():
    c = CronExpr.parse("0 * * * *")
    assert c.next_after(_dt(2024, 1, 1, 9, 30)) == _dt(2024, 1, 1, 10, 0)


def test_next_after_day_rollover():
    c = CronExpr.parse("30 2 * * *")
    assert c.next_after(_dt(2024, 1, 1, 3, 0)) == _dt(2024, 1, 2, 2, 30)


def test_next_after_month_rollover():
    c = CronExpr.parse("0 0 1 * *")
    assert c.next_after(_dt(2024, 1, 15, 12, 0)) == _dt(2024, 2, 1, 0, 0)


def test_next_after_year_rollover():
    c = CronExpr.parse("0 0 1 1 *")
    assert c.next_after(_dt(2024, 6, 1, 0, 0)) == _dt(2025, 1, 1, 0, 0)


def test_next_after_leap_day():
    # Feb 29 exists in 2024 (leap); next after 2023 lands on 2024-02-29.
    c = CronExpr.parse("0 0 29 2 *")
    assert c.next_after(_dt(2023, 3, 1, 0, 0)) == _dt(2024, 2, 29, 0, 0)


def test_next_after_strictly_after():
    c = CronExpr.parse("* * * * *")
    # Exactly on a matching minute -> the NEXT minute.
    assert c.next_after(_dt(2024, 1, 1, 0, 0)) == _dt(2024, 1, 1, 0, 1)


def test_schedule_row_roundtrip():
    s = Schedule(
        id="abc123", name="nightly", objective="audit repo",
        cron="0 2 * * *", repo="/tmp/x", swarm_adapter="openai",
        driver="qwen", enabled=False, max_tokens=5000, max_seconds=600,
        max_swarms=3, created_at=1234.5, last_run_at=99.0, last_status="ok")
    row = s.to_row()
    assert row["enabled"] == 0  # bool flattened to int for sqlite
    back = Schedule.from_row(row)
    assert back == s


def test_schedule_from_row_defaults():
    row = {"id": "x", "name": "n", "objective": "o", "cron": "* * * * *"}
    s = Schedule.from_row(row)
    assert s.enabled is True
    assert s.swarm_adapter == "demo"
    assert s.max_tokens == 0
