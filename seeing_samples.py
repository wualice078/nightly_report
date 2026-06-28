#!/usr/bin/env python3
"""ESO DIMM samples from ~/logs/dimm.logs (written by ntt_dome_status on the mountain)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dome_daemon import belongs_to_ut_night, utc_to_ut_decimal
from weather_samples import to_night_ut

DIMM_LOG_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z\s+([\d.]+)(?:\s+(\S+))?\s*$"
)
# Nearest dimm.logs sample within 10 min of exposure UT (~60 s sampling).
SEEING_JOIN_TOL = 10.0 / 60.0


@dataclass(frozen=True)
class SeeingSample:
    ut: float
    arcsec: str


def format_arcsec(val: float) -> str:
    return f"{val:.3f}"


def _parse_log_line(line: str) -> tuple[datetime, str] | None:
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
    """Load UTC-stamped arcsec lines from dimm.logs for one UT night."""
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


def load_seeing_samples(path: Path | None, night_date: str) -> list[SeeingSample]:
    """Alias for load_dimm_samples."""
    return load_dimm_samples(path, night_date)


def nearest_seeing_on_night(
    night_ut: float,
    samples: list[SeeingSample],
    anchor: float,
    max_delta: float = SEEING_JOIN_TOL,
) -> SeeingSample | None:
    """Nearest DIMM sample on the continuous night timeline."""
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
    """Nearest dimm.logs sample on the night timeline, or n/a if none within tolerance."""
    hit = nearest_seeing_on_night(night_ut, samples, anchor)
    return hit.arcsec if hit else "n/a"


def archive_and_clear_dimm_log(
    log_path: Path,
    night_date: str,
    archive_path: Path | None = None,
) -> int:
    """Archive this night's dimm.logs lines, then truncate the live file."""
    return _archive_and_clear_log(log_path, night_date, archive_path)


def archive_and_clear_seeing_log(
    log_path: Path,
    night_date: str,
    archive_path: Path | None = None,
) -> int:
    """Alias for archive_and_clear_dimm_log."""
    return archive_and_clear_dimm_log(log_path, night_date, archive_path)


def _lines_for_night(log_path: Path, night_date: str) -> list[str]:
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
    lines = _lines_for_night(log_path, night_date)
    if archive_path is not None and lines:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if log_path.is_file():
        log_path.write_text("", encoding="utf-8")
    return len(lines)
