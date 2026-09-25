#!/usr/bin/env python3
"""Tests for questctl shutter-bit and CLOSE_CODE close detection."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build.build_dome_report import dome_summary
from lib.practice_config import PRACTICE_QUESTCTL_LOG_DIR
from lib.questctl_log import (
    count_questctl_closes_on_night,
    find_night_close_from_dome_bits,
    find_night_close_from_questctl,
    load_questctl_closes,
    questctl_logs_for_night,
    shutter_opens_and_closes,
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


def _bit_log(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "questctl.20260604195015.log"
    p.write_text(text)
    return d


def test_shutter_1_2_0_is_close() -> None:
    t0 = datetime(2026, 6, 4, 22, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 5, 7, 44, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 5, 7, 46, tzinfo=timezone.utc)
    opens, closes = shutter_opens_and_closes(
        [(t0, 0), (t0, 2), (t0, 1), (t1, 2), (t2, 0)]
    )
    assert len(opens) == 1 and opens[0] == t0
    assert len(closes) == 1 and closes[0] == t2


def test_shutter_0_2_0_is_not_close() -> None:
    t0 = datetime(2026, 6, 1, 18, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 1, 18, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 6, 1, 18, 2, tzinfo=timezone.utc)
    opens, closes = shutter_opens_and_closes([(t0, 0), (t1, 2), (t2, 0)])
    assert opens == []
    assert closes == []


def test_find_close_from_synthetic_bit_log() -> None:
    # 2026-06-05 07:46:06 UTC = 1780645566; belongs to UT night 20260604
    d = _bit_log(
        "\n".join(
            [
                "checking telescope status 1780516800",
                "dome status bit is 0",
                "checking telescope status 1780524000",
                "dome status bit is 2",
                "checking telescope status 1780524060",
                "dome status bit is 1",
                "checking telescope status 1780645489",
                "dome status bit is 2",
                "checking telescope status 1780645566",
                "dome status bit is 0",
                "",
            ]
        )
    )
    found = find_night_close_from_dome_bits(
        d,
        "20260604",
        first_open=22.0,
        exposure_ut=[23.0, 7.0],
        scheduler_events=[(22.0, "open")],
    )
    assert found is not None
    close_ut, close_utc = found
    assert close_utc.hour == 7 and close_utc.minute == 46
    assert abs(close_ut - 7.768) < 0.01
    for p in d.iterdir():
        p.unlink()
    d.rmdir()


def test_dome_summary_prefers_bits_over_close_code() -> None:
    d = _bit_log(
        "\n".join(
            [
                "checking telescope status 1780524060",
                "dome status bit is 1",
                "checking telescope status 1780645566",
                "dome status bit is 0",
                "signal code has been set to CLOSE_CODE 1780649000",
                "",
            ]
        )
    )
    line = (
        "UT    :  22.00000  LST   :  21.887900  RA    :  21.858631  "
        "Dec   : -29.288111  dome  : open  Focus :  27.970  Filter: UNKNOWN  "
        "Temp  :  13.5  Humid :   9.0  Wnd Sp:   9.0  Wnd Dr:  52.0\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(line)
        sched = Path(f.name)
    summary = dome_summary(
        sched,
        night_date="20260604",
        questctl_log_dir=d,
        exposure_ut=[23.0, 7.0],
    )
    assert summary is not None
    assert summary.last_close_source == "questctl"
    assert summary.close_note is not None and "1→2→0" in summary.close_note
    assert summary.close_utc is not None
    assert summary.close_utc.hour == 7
    sched.unlink()
    for p in d.iterdir():
        p.unlink()
    d.rmdir()


def test_dome_summary_accepts_questctl_dir() -> None:
    from lib.night_paths import resolve_night_paths
    from build.build_exposure_report import exposure_ut_list

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


def test_20260603_actions_and_observing_slot() -> None:
    from build.build_exposure_report import exposure_ut_list
    from lib.night_paths import resolve_night_paths

    paths = resolve_night_paths("20260603", allow_practice_fallback=True)
    exp_ut = exposure_ut_list(paths.log_obs)
    summary = dome_summary(
        paths.scheduler_log,
        night_date=paths.date,
        dome_daemon_log=paths.dome_daemon_log,
        questctl_log_dir=paths.questctl_log_dir,
        exposure_ut=exp_ut,
    )
    assert summary is not None
    actions = summary.actions
    assert any(a == "OPEN" and s == "questctl bits" for _u, a, s in actions)
    assert any(a == "CLOSED" and s == "questctl bits" for _u, a, s in actions)
    assert any(a == "OPEN" and s == "scheduler" for _u, a, s in actions)
    # observing slot is the science open (~22.99), not the 22:00 test
    assert summary.first_open is not None
    assert abs(summary.first_open - 22.99194) < 0.01
    assert summary.last_close is None


def main() -> int:
    tests = [
        test_questctl_logs_for_june_night,
        test_long_running_log_filename,
        test_load_close_code_epochs,
        test_find_close_after_open,
        test_shutter_1_2_0_is_close,
        test_shutter_0_2_0_is_not_close,
        test_find_close_from_synthetic_bit_log,
        test_dome_summary_prefers_bits_over_close_code,
        test_dome_summary_accepts_questctl_dir,
        test_20260603_actions_and_observing_slot,
    ]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
