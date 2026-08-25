#!/usr/bin/env python3
"""
Load ESO DIMM seeing samples from ``dimm.logs``.

On the mountain, ``ntt_dome_status`` appends lines like
``2026-06-24T15:00:00Z 0.662`` to ``~/logs/dimm.logs`` roughly every 60 s.
The exposure table joins the nearest sample within 10 minutes of each exposure UT.

After a successful **morning** live report, :func:`archive_and_clear_dimm_log`
copies this night's lines to ``data/YYYYMMDD/logs/dimm.logs`` and truncates the
live file (see :mod:`make_report`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lib.dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from lib.weather_samples import to_night_ut

DIMM_LOG_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\s+([\d.]+)(?:\s+(\S+))?\s*$"
)
# Nearest dimm.logs sample within 10 min of exposure UT (~60 s sampling).
SEEING_JOIN_TOL = 10.0 / 60.0


@dataclass(frozen=True)
class SeeingSample:
    """One DIMM arcsec measurement at decimal UT hours."""

    ut: float
    arcsec: str


def format_arcsec(val: float) -> str:
    """Format arcsec to three decimal places for report columns."""
    return f"{val:.3f}"


def _parse_log_line(line: str) -> tuple[datetime, str] | None:
    """Parse one ``dimm.logs`` line into ``(utc_datetime, arcsec_string)``."""
    m = DIMM_LOG_LINE.match(line.strip())
    if not m:
        return None
    try:
        utc_dt = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        arcsec = format_arcsec(float(m.group(2)))
    except ValueError:
        return None
    return utc_dt, arcsec


def load_dimm_samples(path: Path | None, night_date: str) -> list[SeeingSample]:
    """
    Load UTC-stamped arcsec lines from ``dimm.logs`` for one UT night.

    Returns samples sorted by UT. Empty when the file is missing or has no
    matching lines.
    """
    if path is None or not path.is_file():
        return []
    out: list[SeeingSample] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _parse_log_line(line)
        if not parsed:
            continue
        utc_dt, arcsec = parsed
        if not belongs_to_ut_night(utc_dt, night_date):
            continue
        out.append(SeeingSample(utc_to_ut_decimal(utc_dt), arcsec))
    out.sort(key=lambda s: s.ut)
    return out


def nearest_seeing_on_night(
    night_ut: float,
    samples: list[SeeingSample],
    anchor: float,
    max_delta: float = SEEING_JOIN_TOL,
) -> SeeingSample | None:
    """
    Return the closest DIMM sample to ``night_ut`` within ``max_delta`` hours.

    Uses the continuous night timeline (:func:`lib.weather_samples.to_night_ut`).
    """
    best: SeeingSample | None = None
    best_d = max_delta + 1.0
    for s in samples:
        d = abs(to_night_ut(s.ut, anchor) - night_ut)
        if d <= max_delta and d < best_d:
            best, best_d = s, d
    return best


def dimm_for_exposure(
    night_ut: float,
    anchor: float,
    samples: list[SeeingSample],
) -> str:
    """
    Return arcsec string for an exposure, or ``n/a`` if no sample is close enough.
    """
    hit = nearest_seeing_on_night(night_ut, samples, anchor)
    return hit.arcsec if hit else "n/a"


def archive_and_clear_dimm_log(
    log_path: Path,
    night_date: str,
    archive_path: Path | None = None,
) -> int:
    """
    Archive this night's ``dimm.logs`` lines, then truncate the live file.

    Returns the number of lines archived. When ``archive_path`` is set and lines
    exist, writes them there before clearing ``log_path``.
    """
    return _archive_and_clear_log(log_path, night_date, archive_path)


def _lines_for_night(log_path: Path, night_date: str) -> list[str]:
    """Collect raw log lines belonging to UT night ``night_date``."""
    if not log_path.is_file():
        return []
    out: list[str] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parsed = _parse_log_line(line)
        if not parsed:
            continue
        utc_dt, _ = parsed
        if belongs_to_ut_night(utc_dt, night_date):
            out.append(line.strip())
    return out


def _archive_and_clear_log(
    log_path: Path,
    night_date: str,
    archive_path: Path | None = None,
) -> int:
    """Internal helper for :func:`archive_and_clear_dimm_log`."""
    lines = _lines_for_night(log_path, night_date)
    if archive_path is not None and lines:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if log_path.is_file():
        log_path.write_text("", encoding="utf-8")
    return len(lines)
