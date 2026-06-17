#!/usr/bin/env python3
"""Tests for dome_daemon.log fallback close detection."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from build_dome_report import dome_summary
from dome_daemon import (
    _parse_daemon_timestamp,
    belongs_to_ut_night,
    find_night_close_from_daemon,
    load_dome_daemon_closes,
    utc_to_ut_decimal,
)
from practice_config import PRACTICE_DOME_DAEMON_LOG


def test_parse_daemon_timestamp() -> None:
  line = "Tue Jun 2 06:07:31 AM -04 2026 iteration 1 : schmidt dome now closed"
  dt = _parse_daemon_timestamp(line)
  assert dt is not None
  utc = dt.astimezone(timezone.utc)
  assert utc.year == 2026 and utc.month == 6 and utc.day == 2
  assert utc.hour == 10 and utc.minute == 7


def test_belongs_to_ut_night() -> None:
  utc = datetime(2026, 6, 2, 10, 7, 31, tzinfo=timezone.utc)
  assert belongs_to_ut_night(utc, "20260601")
  assert not belongs_to_ut_night(utc, "20260602")


def test_load_practice_daemon_closes() -> None:
  closes = load_dome_daemon_closes(PRACTICE_DOME_DAEMON_LOG)
  assert len(closes) == 3


def test_find_close_for_june_night() -> None:
  found = find_night_close_from_daemon(
      PRACTICE_DOME_DAEMON_LOG,
      "20260601",
      first_open=22.5,
      exposure_ut=[23.0, 8.5],
      scheduler_events=[(22.5, "open")],
  )
  assert found is not None
  close_ut, close_utc = found
  assert abs(close_ut - 10.125277) < 0.01
  assert close_utc.hour == 10


def test_scheduler_close_preferred() -> None:
  from night_paths import resolve_night_paths

  paths = resolve_night_paths("20260529", allow_practice_fallback=True)
  summary = dome_summary(
      paths.scheduler_log,
      night_date=paths.date,
      dome_daemon_log=paths.dome_daemon_log,
      exposure_ut=[10.0],
  )
  assert summary is not None
  assert summary.last_close_source == "scheduler"
  assert abs(summary.last_close - 10.138889) < 0.001


def main() -> int:
  tests = [
      test_parse_daemon_timestamp,
      test_belongs_to_ut_night,
      test_load_practice_daemon_closes,
      test_find_close_for_june_night,
      test_scheduler_close_preferred,
  ]
  for t in tests:
      t()
      print(f"  ok  {t.__name__}")
  print(f"\n{len(tests)} passed")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
