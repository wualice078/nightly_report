#!/usr/bin/env python3
"""
Build and email the LS4 nightly report.

Mountain production:
  python3 /home/observer/nightly_report/send_report_email.py --no-practice-fallback --to EMAIL

Practice / test:
  python3 /home/observer/nightly_report/send_report_email.py --date YYYYMMDD --build-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPORTS = PACKAGE / "reports"
sys.path.insert(0, str(PACKAGE))

from build_dome_report import build_dome_section
from build_exposure_report import build_exposure_section, exposure_ut_list
from build_weather_report import build_weather_section
from compare_obsplan_log import build_fields_section
from night_paths import NightPaths, get_default_ut_date, resolve_night_paths


def build_missing_report(date: str, error: str) -> str:
    return (
        f"LS4 NIGHTLY REPORT — {date}\n"
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Status: DATA MISSING\n\n"
        f"=== Data unavailable ===\n  {error}\n\n"
    )


def build_full_report(paths: NightPaths) -> str:
    exp_ut = exposure_ut_list(paths.log_obs)
    header = (
        f"LS4 NIGHTLY REPORT — {paths.date}\n"
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Data source: {paths.source}\n\n"
    )
    return "".join(
        [
            header,
            build_fields_section(paths.obsplan, paths.log_obs),
            "\n",
            build_exposure_section(paths.log_obs, paths.scheduler_log),
            build_dome_section(paths.scheduler_log),
            build_weather_section(paths.scheduler_log, exposure_ut=exp_ut),
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--to")
    ap.add_argument("--build-only", action="store_true")
    ap.add_argument("--no-practice-fallback", action="store_true")
    ap.add_argument("--subject")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    date = args.date or get_default_ut_date()
    REPORTS.mkdir(exist_ok=True)
    report = args.report or (REPORTS / f"report_{date}.txt")
    practice = not args.no_practice_fallback

    paths = None
    try:
        paths = resolve_night_paths(date, allow_practice_fallback=practice)
        text = build_full_report(paths)
        print(f"Night {date} — source: {paths.source}")
    except FileNotFoundError as e:
        if practice:
            print(f"error: {e}", file=sys.stderr)
            return 1
        text = build_missing_report(date, str(e))

    report.write_text(text)
    print(f"Wrote {report}")

    if args.build_only or not args.to:
        return 0

    practice_tag = " [PRACTICE]" if paths and paths.source == "practice" else ""
    r = subprocess.run(
        ["mail", "-s", args.subject or f"LS4 nightly report {date}{practice_tag}", "-a", str(report), args.to],
        input=f"LS4 nightly report attached.{practice_tag}\n",
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout or "mail failed", file=sys.stderr)
        return 1
    print(f"Sent to {args.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
