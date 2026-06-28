#!/usr/bin/env python3
"""
Build and email the LS4 nightly report.

Mountain:
  python3 send_report_email.py --build-only
  python3 send_report_email.py --date YYYYMMDD --build-only

Practice:
  python3 send_report_email.py --date YYYYMMDD --build-only --practice-fallback
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

from build_dome_report import build_dome_section
from build_exposure_report import build_exposure_section, exposure_ut_list
from build_summary import build_summary_section
from build_weather_report import build_weather_section
from compare_obsplan_log import build_fields_section
from night_paths import NightPaths, get_default_ut_date, resolve_night_paths
from practice_config import DIMM_LOG, MORNING_REPORT_LIVE_ONLY
from seeing_samples import archive_and_clear_dimm_log


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--to")
    ap.add_argument("--build-only", action="store_true")
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

    if args.build_only or not args.to:
        return 0

    if shutil.which("mail") is None:
        print(
            f"warning: 'mail' not installed — report saved at {report}",
            file=sys.stderr,
        )
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
