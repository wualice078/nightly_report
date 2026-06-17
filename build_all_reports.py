#!/usr/bin/env python3
"""
Build and store text reports for all available live nights.

Writes one file per night under nightly_report/reports/report_YYYYMMDD.txt
(same location as the morning cron job).

Usage:
  python3 build_all_reports.py
  python3 build_all_reports.py --date 20260608 --date 20260609
  python3 build_all_reports.py --no-practice-fallback
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def main() -> int:
    sys.path.insert(0, str(PACKAGE))
    from night_paths import discover_live_nights, practice_night_list

    ap = argparse.ArgumentParser(description="Build stored nightly reports for many UT nights")
    ap.add_argument("--date", action="append", help="One UT night (repeatable); default: all live nights")
    ap.add_argument("--practice-fallback", action="store_true", help="Use practice archive if live logs missing")
    ap.add_argument("--no-practice-fallback", action="store_true", help="Live data only")
    args = ap.parse_args()

    if args.date:
        nights = args.date
    elif args.no_practice_fallback:
        nights = discover_live_nights()
    else:
        nights = discover_live_nights() or practice_night_list()

    if not nights:
        print("No nights found to build.", file=sys.stderr)
        return 1

    cmd_base = [sys.executable, str(PACKAGE / "send_report_email.py"), "--build-only"]
    if args.no_practice_fallback:
        cmd_base.append("--no-practice-fallback")

    ok, fail = 0, 0
    for date in nights:
        r = subprocess.run([*cmd_base, "--date", date], cwd=str(PACKAGE))
        if r.returncode == 0:
            ok += 1
        else:
            fail += 1
            print(f"FAILED {date}", file=sys.stderr)

    print(f"Built {ok} report(s), {fail} failed -> {PACKAGE / 'reports'}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
