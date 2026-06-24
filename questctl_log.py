#!/usr/bin/env python3
"""Parse dome close times from questctl logs (manual closedome / operator signal)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from weather_samples import night_anchor_ut, to_night_ut

CLOSE_CODE = re.compile(r"signal code has been set to CLOSE_CODE\s+(\d+)")


def questctl_logs_for_night(log_dir: Path | None, night_date: str) -> list[Path]:
    """questctl.YYYYMMDDHHMMSS.log files that may cover this UT night."""
    if log_dir is None or not log_dir.is_dir():
        return []
    d0 = datetime.strptime(night_date, "%Y%m%d")
    prev = (d0 - timedelta(days=1)).strftime("%Y%m%d")
    allowed = {night_date, prev}
    out: list[Path] = []
    for path in sorted(log_dir.glob("questctl.*.log")):
        parts = path.name.split(".")
        if len(parts) < 2 or len(parts[1]) < 8:
            continue
        if parts[1][:8] in allowed:
            out.append(path)
    return out


def load_questctl_closes(log_dir: Path | None, night_date: str) -> list[datetime]:
    """UTC datetimes from questctl CLOSE_CODE lines for logs tied to night_date."""
    out: list[datetime] = []
    for path in questctl_logs_for_night(log_dir, night_date):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = CLOSE_CODE.search(line)
            if not m:
                continue
            out.append(datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc))
    return out


def count_questctl_closes_on_night(log_dir: Path | None, night_date: str) -> int:
    return sum(1 for c in load_questctl_closes(log_dir, night_date) if belongs_to_ut_night(c, night_date))


def find_night_close_from_questctl(
    log_dir: Path | None,
    night_date: str,
    first_open: float,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """
    Last questctl CLOSE_CODE for this UT night after dome open.

    Typical path: observer runs closedome → signal to questctl → CLOSE_CODE logged.
  """
    closes = load_questctl_closes(log_dir, night_date)
    if not closes:
        return None

    anchor = night_anchor_ut(scheduler_events, exposure_ut)
    open_night = to_night_ut(first_open, anchor)
    last_exp_night = max(to_night_ut(u, anchor) for u in exposure_ut) if exposure_ut else None

    candidates: list[tuple[float, float, datetime]] = []
    for utc_dt in closes:
        if not belongs_to_ut_night(utc_dt, night_date):
            continue
        ut = utc_to_ut_decimal(utc_dt)
        night_ut = to_night_ut(ut, anchor)
        if night_ut + 1e-6 < open_night:
            continue
        candidates.append((night_ut, ut, utc_dt))

    if not candidates:
        return None

    if last_exp_night is not None:
        after_exp = [c for c in candidates if c[0] >= last_exp_night - 0.25]
        if after_exp:
            best = max(after_exp, key=lambda x: x[0])
            return best[1], best[2]

    best = max(candidates, key=lambda x: x[0])
    return best[1], best[2]
