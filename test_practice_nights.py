#!/usr/bin/env python3
"""
Build reports for practice nights and check basic consistency with raw logs.

Usage:
  python3 test_practice_nights.py              # all nights in practice_config
  python3 test_practice_nights.py --date 20260517
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from build_exposure_report import _is_observing, _parse_line
from compare_obsplan_log import is_observing_field, parse_obsplan, parse_log_obs
from practice_config import PRACTICE_ROOT
from send_report_email import build_full_report
from night_paths import discover_practice_nights, practice_night_list, resolve_night_paths

REPORTS = PACKAGE / "reports"


def _count_exposures(log_obs: Path) -> tuple[int, int, int]:
    obs, cal = 0, 0
    for line in log_obs.read_text().splitlines():
        row = _parse_line(line.strip())
        if not row:
            continue
        if row["observing"]:
            obs += 1
        else:
            cal += 1
    return obs + cal, obs, cal


def validate(date: str, paths, report: str) -> list[str]:
    errors = []
    log_lines = parse_log_obs(paths.log_obs)
    total, obs_n, cal_n = _count_exposures(paths.log_obs)

    m_obs = re.search(r"Observing \((\d+)\)", report)
    m_cal = re.search(r"Calibration \((\d+)\)", report)
    if not m_obs or int(m_obs.group(1)) != obs_n:
        errors.append(f"observing count: report={m_obs.group(1) if m_obs else '?'} log={obs_n}")
    if not m_cal or int(m_cal.group(1)) != cal_n:
        errors.append(f"calibration count: report={m_cal.group(1) if m_cal else '?'} log={cal_n}")

    if f"exposures in log: {len(log_lines)}" not in report:
        errors.append(f"log.obs line count {len(log_lines)} not in report header")

    planned = parse_obsplan(paths.obsplan)
    obs_fields = [f for f in planned if is_observing_field(f)]
    if f"Observing fields ({len(obs_fields)} planned)" not in report:
        errors.append(f"observing field count {len(obs_fields)} mismatch in report")

    if paths.scheduler_log and paths.scheduler_log.is_file():
        if "=== Dome ===" not in report:
            errors.append("missing dome section")
        if "=== Weather" not in report:
            errors.append("missing weather section")
    else:
        if "note:" not in report.lower() and "no dome" not in report.lower():
            pass  # ok

    if f"Data source: practice" not in report:
        errors.append("not marked as practice source")

    return errors


def run_night(date: str, *, write_report: bool = True) -> tuple[bool, str]:
    try:
        paths = resolve_night_paths(date, allow_practice_fallback=True)
    except FileNotFoundError as e:
        return False, str(e)

    report = build_full_report(paths)
    errors = validate(date, paths, report)

    if write_report:
        REPORTS.mkdir(exist_ok=True)
        out = REPORTS / f"report_{date}.txt"
        out.write_text(report)

    if errors:
        return False, "; ".join(errors)
    sched = "yes" if paths.scheduler_log else "no sched log"
    total, obs_n, cal_n = _count_exposures(paths.log_obs)
    return True, f"{total} exposures ({obs_n} obs, {cal_n} cal), scheduler log: {sched}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", action="append", help="Test one night (repeatable)")
    ap.add_argument("--no-write", action="store_true", help="Do not write report files")
    args = ap.parse_args()

    nights = args.date if args.date else practice_night_list()
    if not nights:
        print(f"No practice nights under {PRACTICE_ROOT}", file=sys.stderr)
        return 1

    ok, fail = 0, 0
    print(f"Testing {len(nights)} night(s) from {PRACTICE_ROOT}\n")
    for date in nights:
        passed, msg = run_night(date, write_report=not args.no_write)
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {date}  {msg}")
        if passed:
            ok += 1
        else:
            fail += 1

    discovered = discover_practice_nights()
    skipped = set(discovered) - set(nights)
    if skipped and not args.date:
        print(f"\n  ({len(skipped)} nights with data but not in PRACTICE_NIGHTS — using all discovered)")

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
