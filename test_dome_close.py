#!/usr/bin/env python3
"""One command: find a night with data, build report, show dome close lines."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from build_dome_report import dome_summary
from build_exposure_report import exposure_ut_list
from night_paths import discover_live_nights, resolve_night_paths
from practice_config import LIVE_DATA_ROOTS, QUESTCTL_LOG_DIR
from questctl_log import count_questctl_closes_on_night

DOME_LINE = re.compile(r"Dome last close|close time|questctl|still open", re.I)


def main() -> int:
    date = sys.argv[1] if len(sys.argv) > 1 else None

    print("Looking for night data in:")
    for root in LIVE_DATA_ROOTS:
        print(f"  {root}")
    print()

    nights = discover_live_nights()
    if not nights:
        print("No nights found (need YYYYMMDD/logs/log.obs + obsplan).")
        return 1

    print(f"Nights with data ({len(nights)}): {', '.join(nights[-10:])}")
    if not date:
        date = nights[-1]
        print(f"Using most recent: {date}\n")
    else:
        print(f"Using: {date}\n")

    try:
        paths = resolve_night_paths(date, allow_practice_fallback=False)
    except FileNotFoundError as e:
        print(f"NO DATA for {date}:\n{e}")
        return 1

    print(f"obsplan:  {paths.obsplan}")
    print(f"log.obs:  {paths.log_obs}")
    print(f"scheduler:{paths.scheduler_log}")
    print(f"questctl: {paths.questctl_log_dir or QUESTCTL_LOG_DIR}")
    n_close = count_questctl_closes_on_night(paths.questctl_log_dir or QUESTCTL_LOG_DIR, date)
    print(f"questctl CLOSE_CODE for UT night {date}: {n_close}\n")

    exp_ut = exposure_ut_list(paths.log_obs)
    summary = dome_summary(
        paths.scheduler_log,
        night_date=date,
        questctl_log_dir=paths.questctl_log_dir or QUESTCTL_LOG_DIR,
        exposure_ut=exp_ut,
    )

    print("=== Dome result ===")
    if summary is None:
        print("  no dome info")
    elif summary.last_close is not None:
        print(f"  first open:  {summary.first_open:.3f} h UT")
        print(f"  last close:  {summary.last_close:.3f} h UT")
        print(f"  source:      {summary.last_close_source}")
        if summary.close_note:
            print(f"  note:        {summary.close_note}")
        if summary.close_utc:
            print(f"  UTC:         {summary.close_utc.isoformat()}")
    elif summary.still_open:
        print(f"  still open from {summary.open_since:.3f} h UT (no close found)")
    else:
        print("  no open/close in scheduler log")

    if n_close == 0:
        print("\n  >> No questctl CLOSE_CODE for this UT night — dome close cannot appear.")
    elif summary and summary.last_close_source != "questctl":
        print("\n  >> CLOSE_CODE exists but was not matched to this night (check open time / exposures).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
