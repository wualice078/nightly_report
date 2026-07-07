#!/usr/bin/env python3
"""One command: find a night with data, build report, show dome close lines."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from build_dome_report import dome_summary
from build_exposure_report import exposure_ut_list
from night_paths import discover_live_nights, resolve_night_paths
from practice_config import LIVE_DATA_ROOTS, QUESTCTL_LOG_DIR
from questctl_log import count_questctl_closes_on_night


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else None

    print("Data folder: /home/observer/data/YYYYMMDD/logs/")
    print("Questctl:    /home/observer/logs/questctl.*.log\n")

    nights = discover_live_nights()
    if not nights:
        print("No nights found (need log.obs + obsplan).")
        return 1

    print(f"Nights with data ({len(nights)}): {', '.join(nights[-10:])}")
    if not date:
        # default to previous complete night, not tonight in progress
        date = nights[-2] if len(nights) >= 2 else nights[-1]
        print(f"Using previous night (not latest): {date}\n")
    else:
        print(f"Using: {date}\n")

    try:
        paths = resolve_night_paths(date, allow_practice_fallback=False)
    except FileNotFoundError as e:
        print(f"NO DATA for {date}:\n{e}")
        return 1

    qdir = paths.questctl_log_dir or QUESTCTL_LOG_DIR
    n_close = count_questctl_closes_on_night(qdir, date)
    exp_ut = exposure_ut_list(paths.log_obs)

    print(f"log.obs:   {paths.log_obs}  ({len(exp_ut)} exposures)")
    print(f"scheduler: {paths.scheduler_log}")
    print(f"questctl CLOSE_CODE for UT night {date}: {n_close}")
    if exp_ut:
        print(f"last exposure UT: {max(exp_ut):.3f} h\n")

    summary = dome_summary(
        paths.scheduler_log,
        night_date=date,
        questctl_log_dir=qdir,
        exposure_ut=exp_ut,
    )

    print("=== Dome result ===")
    if summary is None:
        print("  no dome info")
        return 1

    if summary.first_open is not None:
        print(f"  first open:  {summary.first_open:.3f} h UT")
    if summary.last_close is not None:
        print(f"  last close:  {summary.last_close:.3f} h UT")
        print(f"  source:      {summary.last_close_source}")
        if summary.close_note:
            print(f"  note:        {summary.close_note}")
        if summary.close_utc:
            print(f"  UTC:         {summary.close_utc.isoformat()}")
    elif summary.still_open:
        print(f"  still open from {summary.open_since:.3f} h UT")
        print("  last close:  n/a (no end-of-night close found yet)")
    else:
        print("  last close:  n/a")

    if summary.last_close_source == "questctl":
        print("\n  OK — dome close from questctl (closedome).")
    elif summary.last_close_source == "scheduler":
        print("\n  OK — dome close from scheduler log (no questctl CLOSE_CODE).")
    elif n_close > 0:
        print("\n  WARN — CLOSE_CODE exists but was not matched (check exposures / open time).")
    elif summary.still_open:
        print("\n  WARN — no end-of-night close; was closedome run?")
    else:
        print("\n  WARN — no dome close found in any log.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
