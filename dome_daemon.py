#!/usr/bin/env python3
"""Parse Schmidt dome open/close events from dome_daemon.log (local Chile time)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from weather_samples import night_anchor_ut, to_night_ut

# Mountain `date` is usually 24h (no AM/PM); practice copies may use 12h.
DAEMON_TS = re.compile(
    r"^(\w{3})\s+(\w{3})\s+(\d+)\s+(\d+):(\d+):(\d+)\s+"
    r"(?:(AM|PM)\s+)?([+-])(\d{2})\s+(\d{4})"
)
DAEMON_CLOSED = re.compile(r"schmidt dome now closed", re.IGNORECASE)

_MONTH = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def _parse_daemon_timestamp(line: str) -> datetime | None:
    m = DAEMON_TS.match(line.strip())
    if not m:
        return None
    _, mon, day_s, h_s, mi_s, s_s, ampm, sign, tz_h, year_s = m.groups()
    month = _MONTH.get(mon)
    if month is None:
        return None
    day = int(day_s)
    hour = int(h_s)
    if ampm:
        hour = hour % 12
        if ampm.upper() == "PM":
            hour += 12
    minute = int(mi_s)
    second = int(s_s)
    year = int(year_s)
    tz_offset = int(f"{sign}{tz_h}")
    tz = timezone(timedelta(hours=tz_offset))
    return datetime(year, month, day, hour, minute, second, tzinfo=tz)


def utc_to_ut_decimal(utc_dt: datetime) -> float:
    u = utc_dt.astimezone(timezone.utc)
    return u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3_600_000_000


def belongs_to_ut_night(utc_dt: datetime, night_date: str) -> bool:
    """True if UTC instant falls in the UT observing night labeled night_date."""
    u = utc_dt.astimezone(timezone.utc)
    d0 = datetime.strptime(night_date, "%Y%m%d").date()
    d1 = d0 + timedelta(days=1)
    ud = u.date()
    ut_h = u.hour + u.minute / 60.0
    if ud == d0 and ut_h >= 12.0:
        return True
    if ud == d1 and ut_h < 18.0:
        return True
    return False


def load_dome_daemon_closes(path: Path | None) -> list[datetime]:
    """Return UTC datetimes of 'schmidt dome now closed' events, in log order."""
    if path is None or not path.is_file():
        return []
    out: list[datetime] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not DAEMON_CLOSED.search(line):
            continue
        local_dt = _parse_daemon_timestamp(line)
        if local_dt is None:
            continue
        out.append(local_dt.astimezone(timezone.utc))
    return out


def count_daemon_closes_on_night(daemon_log: Path | None, night_date: str) -> int:
    return sum(1 for c in load_dome_daemon_closes(daemon_log) if belongs_to_ut_night(c, night_date))


def find_night_close_from_daemon(
    daemon_log: Path | None,
    night_date: str,
    first_open: float,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """
    Last dome_daemon close for this UT night, after first open.

    Returns (scheduler-style UT decimal hours, UTC datetime).
    """
    closes = load_dome_daemon_closes(daemon_log)
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
