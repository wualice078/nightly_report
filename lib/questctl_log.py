#!/usr/bin/env python3
"""
Parse dome close times from questctl logs (manual ``closedome``).

When an operator runs ``closedome``, questctl logs a ``CLOSE_CODE`` line with a
Unix epoch timestamp. This is the **primary** source for end-of-night dome close
time in the nightly report.

Note: questctl log filenames reflect the process **start** time; a single log may
span weeks. Always filter ``CLOSE_CODE`` events by UTC timestamp, not filename.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from lib.dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from lib.weather_samples import night_anchor_ut, to_night_ut

CLOSE_CODE = re.compile(r"signal code has been set to CLOSE_CODE\s+(\d+)")


def questctl_logs_for_night(log_dir: Path | None, night_date: str) -> list[Path]:
    """
    Return all ``questctl.*.log`` files to scan for a UT night.

    ``night_date`` is accepted for API symmetry; filtering is done by
    :func:`load_questctl_closes` using each ``CLOSE_CODE`` epoch.
    """
    _ = night_date  # filtering is by CLOSE_CODE epoch in load_questctl_closes
    if log_dir is None or not log_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(log_dir.glob("questctl.*.log")):
        parts = path.name.split(".")
        if len(parts) < 2:
            continue
        out.append(path)
    return out


def _close_code_lines(path: Path):
    """
    Yield lines containing ``CLOSE_CODE`` without loading the whole log into RAM.

    Uses ``grep`` when available; falls back to a streaming file read.
    """
    import subprocess

    try:
        r = subprocess.run(
            ["grep", "CLOSE_CODE", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if r.stdout:
            yield from r.stdout.splitlines()
        return
    except (OSError, FileNotFoundError):
        pass

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "CLOSE_CODE" in line:
                yield line


def recent_questctl_closes(log_dir: Path | None, *, limit: int = 5) -> list[tuple[datetime, Path]]:
    """
    Return the most recent ``CLOSE_CODE`` events across all questctl logs.

    Useful for diagnostics when a night has no matching close (see
    :mod:`tools.check_night`).
    """
    found: list[tuple[datetime, Path]] = []
    for path in reversed(questctl_logs_for_night(log_dir, "")):
        for line in _close_code_lines(path):
            m = CLOSE_CODE.search(line)
            if not m:
                continue
            found.append(
                (datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc), path)
            )
        if len(found) >= limit:
            break
    return sorted(found, key=lambda x: x[0])[-limit:]


def load_questctl_closes(log_dir: Path | None, night_date: str) -> list[datetime]:
    """
    Return UTC datetimes from ``CLOSE_CODE`` lines belonging to UT night ``night_date``.
    """
    out: list[datetime] = []
    for path in questctl_logs_for_night(log_dir, night_date):
        for line in _close_code_lines(path):
            m = CLOSE_CODE.search(line)
            if not m:
                continue
            utc_dt = datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)
            if belongs_to_ut_night(utc_dt, night_date):
                out.append(utc_dt)
    return out


def count_questctl_closes_on_night(log_dir: Path | None, night_date: str) -> int:
    """Count ``CLOSE_CODE`` events on UT night ``night_date``."""
    return len(load_questctl_closes(log_dir, night_date))


def find_night_close_from_questctl(
    log_dir: Path | None,
    night_date: str,
    first_open: float,
    exposure_ut: list[float],
    scheduler_events: list[tuple[float, str]],
) -> tuple[float, datetime] | None:
    """
    Pick the best questctl close for end-of-night reporting.

    Typical path: operator runs ``closedome`` → questctl logs ``CLOSE_CODE``.
    Prefers the latest close after dome open and (when possible) after the last
    exposure. Returns ``(ut_decimal, utc_datetime)`` or None.
    """
    closes = load_questctl_closes(log_dir, night_date)
    if not closes:
        return None

    anchor = night_anchor_ut(scheduler_events, exposure_ut)
    open_night = to_night_ut(first_open, anchor)
    last_exp_night = max(to_night_ut(u, anchor) for u in exposure_ut) if exposure_ut else None

    candidates: list[tuple[float, float, datetime]] = []
    for utc_dt in closes:
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
