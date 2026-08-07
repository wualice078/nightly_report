#!/usr/bin/env python3
"""
Build one night's LS4 report. Writes reports/report_YYYYMMDD.txt; only emails
when given a recipient.

Mountain:
  python3 make_report.py
  python3 make_report.py --date YYYYMMDD
  python3 make_report.py --morning            # what cron_morning.sh runs

Practice:
  python3 make_report.py --date YYYYMMDD --practice-fallback
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPORTS = PACKAGE / "reports"
sys.path.insert(0, str(PACKAGE))

from build.build_dome_report import build_dome_section
from build.build_exposure_report import build_exposure_section, exposure_ut_list
from build.build_summary import build_summary_section
from build.build_weather_report import build_weather_section
from build.compare_obsplan_log import build_fields_section
from lib.night_paths import NightPaths, get_default_ut_date, resolve_night_paths
from lib.practice_config import DIMM_LOG, MORNING_REPORT_EMAIL, MORNING_REPORT_LIVE_ONLY
from lib.seeing_samples import archive_and_clear_dimm_log


def build_missing_report(date: str, error: str) -> str:
    return (
        f"LS4 NIGHTLY REPORT - {date}\n"
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Status: DATA MISSING\n\n"
        f"=== Data unavailable ===\n  {error}\n\n"
    )


def build_full_report(paths: NightPaths) -> str:
    exp_ut = exposure_ut_list(paths.log_obs)
    header = (
        f"LS4 NIGHTLY REPORT - {paths.date}\n"
        f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Data source: {paths.source}\n\n"
    )
    return "".join(
        [
            header,
            build_summary_section(
                paths.obsplan,
                paths.log_obs,
                paths.scheduler_log,
                night_date=paths.date,
                dome_daemon_log=paths.dome_daemon_log,
                questctl_log_dir=paths.questctl_log_dir,
                exposure_ut=exp_ut,
            ),
            build_fields_section(paths.obsplan, paths.log_obs),
            "\n",
            build_exposure_section(
                paths.log_obs,
                paths.scheduler_log,
                night_date=paths.date,
                dimm_log=paths.dimm_log,
            ),
            build_dome_section(
                paths.scheduler_log,
                night_date=paths.date,
                dome_daemon_log=paths.dome_daemon_log,
                questctl_log_dir=paths.questctl_log_dir,
                exposure_ut=exp_ut,
            ),
            build_weather_section(paths.scheduler_log, exposure_ut=exp_ut),
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="UT night YYYYMMDD (default: last night)")
    ap.add_argument("--to", help="Email the report to this address")
    ap.add_argument(
        "--morning",
        action="store_true",
        help=f"Cron mode: email the configured recipient ({MORNING_REPORT_EMAIL})",
    )
    # Reports are only emailed when a recipient is given, so this is a no-op kept
    # so older cron lines and scripts do not break.
    ap.add_argument("--build-only", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--practice-fallback", action="store_true", help="Use practice archive if live logs missing")
    ap.add_argument("--no-practice-fallback", action="store_true", help="Live data only (same as mountain default)")
    ap.add_argument("--subject")
    ap.add_argument("--report", type=Path)
    ap.add_argument(
        "--cleanup-seeing",
        action="store_true",
        help="Archive dimm.logs to the night data dir and truncate the live file",
    )
    ap.add_argument(
        "--no-cleanup-seeing",
        action="store_true",
        help="Do not archive/truncate dimm.logs after build",
    )
    args = ap.parse_args()

    recipient = MORNING_REPORT_EMAIL if args.morning else args.to
    date = args.date or get_default_ut_date()
    REPORTS.mkdir(exist_ok=True)
    report = args.report or (REPORTS / f"report_{date}.txt")
    if args.no_practice_fallback:
        allow_practice = False
    elif args.practice_fallback:
        allow_practice = True
    else:
        allow_practice = not MORNING_REPORT_LIVE_ONLY

    paths = None
    try:
        paths = resolve_night_paths(date, allow_practice_fallback=allow_practice)
        text = build_full_report(paths)
        print(f"Night {date} - source: {paths.source}")
    except FileNotFoundError as e:
        if allow_practice:
            print(f"error: {e}", file=sys.stderr)
            return 1
        text = build_missing_report(date, str(e))

    report.write_text(text)
    print(f"Wrote {report}")

    if paths is not None and "DATA MISSING" not in text:
        cleanup = args.cleanup_seeing or (
            not args.no_cleanup_seeing
            and args.date is None
            and paths.source == "live"
        )
        if cleanup:
            archive = paths.log_obs.parent / "dimm.logs"
            try:
                n = archive_and_clear_dimm_log(DIMM_LOG, paths.date, archive)
                print(f"Cleared dimm.logs ({n} samples archived to {archive})")
            except OSError as exc:
                print(
                    f"warning: dimm.logs cleanup skipped ({exc}); report was still written",
                    file=sys.stderr,
                )

    if not recipient:
        return 0

    if shutil.which("mail") is None:
        print(
            f"warning: 'mail' not installed — report saved at {report}",
            file=sys.stderr,
        )
        return 0

    practice_tag = " [PRACTICE]" if paths and paths.source == "practice" else ""
    r = subprocess.run(
        ["mail", "-s", args.subject or f"LS4 nightly report {date}{practice_tag}", "-a", str(report), recipient],
        input=f"LS4 nightly report attached.{practice_tag}\n",
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout or "mail failed", file=sys.stderr)
        return 1
    print(f"Sent to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
