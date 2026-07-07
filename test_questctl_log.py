#!/usr/bin/env python3
"""Tests for questctl.log CLOSE_CODE close detection."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from build_dome_report import dome_summary
from practice_config import PRACTICE_QUESTCTL_LOG_DIR
from questctl_log import (
    count_questctl_closes_on_night,
    find_night_close_from_questctl,
    load_questctl_closes,
    questctl_logs_for_night,
)


def test_questctl_logs_for_june_night() -> None:
    logs = questctl_logs_for_night(PRACTICE_QUESTCTL_LOG_DIR, "20260601")
    assert len(logs) >= 1


def test_long_running_log_filename() -> None:
    """CLOSE for UT night 20260601 lives in questctl.20260601181324.log."""
    logs = questctl_logs_for_night(PRACTICE_QUESTCTL_LOG_DIR, "20260602")
    assert any("20260601" in p.name for p in logs)
    assert count_questctl_closes_on_night(PRACTICE_QUESTCTL_LOG_DIR, "20260601") >= 1


def test_load_close_code_epochs() -> None:
    closes = load_questctl_closes(PRACTICE_QUESTCTL_LOG_DIR, "20260601")
    assert len(closes) >= 3
    assert count_questctl_closes_on_night(PRACTICE_QUESTCTL_LOG_DIR, "20260601") >= 3


def test_find_close_after_open() -> None:
    found = find_night_close_from_questctl(
        PRACTICE_QUESTCTL_LOG_DIR,
        "20260601",
        first_open=22.2,
        exposure_ut=[23.0, 8.5],
        scheduler_events=[(22.2, "open")],
    )
    assert found is not None
    close_ut, close_utc = found
    assert close_utc.hour == 10 and close_utc.minute == 7
    assert abs(close_ut - 10.125) < 0.02


def test_dome_summary_accepts_questctl_dir() -> None:
    from night_paths import resolve_night_paths
    from build_exposure_report import exposure_ut_list

    paths = resolve_night_paths("20260530", allow_practice_fallback=True)
    exp_ut = exposure_ut_list(paths.log_obs)
    summary = dome_summary(
        paths.scheduler_log,
        night_date=paths.date,
        dome_daemon_log=paths.dome_daemon_log,
        questctl_log_dir=paths.questctl_log_dir,
        exposure_ut=exp_ut,
    )
    assert summary is not None
    assert summary.first_open is not None


def main() -> int:
    tests = [
        test_questctl_logs_for_june_night,
        test_long_running_log_filename,
        test_load_close_code_epochs,
        test_find_close_after_open,
        test_dome_summary_accepts_questctl_dir,
    ]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
