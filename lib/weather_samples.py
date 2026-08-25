#!/usr/bin/env python3
"""
Parse scheduler weather and dome status lines for nightly reports.

The scheduler log (``YYYYMMDD.log``) contains periodic lines with Temp, Humid,
wind speed, and wind direction, plus dome open/closed state changes. This module
extracts those samples and provides helpers for the **continuous night timeline**
(UT hours after midnight are mapped to 24–48 h so sorting and joins work across
local midnight).

Used by:

    :mod:`build.build_weather_report` — 30-minute weather grid
    :mod:`build.build_exposure_report` — nearest weather per exposure
    :mod:`build.build_dome_report` — dome event timeline and close resolution
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

WEATHER_LINE = re.compile(
    r"UT\s*:\s*([\d.]+)\s+.*?Temp\s*:\s*([\d.]+)\s+Humid\s*:\s*([\d.]+)\s+"
    r"Wnd Sp:\s*([\d.]+)\s+Wnd Dr:\s*([\d.]+)",
    re.IGNORECASE,
)
DOME_LINE = re.compile(
    r"UT\s*:\s*([\d.]+)\s+.*?\bdome\s*:\s*(\w+)",
    re.IGNORECASE,
)

GRID_STEP = 0.5  # 30 minutes in decimal UT hours


def _read_log(path: Path) -> str:
    """Read a log file as UTF-8 text, replacing undecodable bytes."""
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class WeatherSample:
    """One scheduler weather reading at decimal UT hours."""

    ut: float
    temp: str
    humid: str
    wind: str
    wind_dir: str


def load_scheduler_weather(path: Path | None) -> list[WeatherSample]:
    """
    Parse Temp/Humid/Wind lines from the scheduler log.

    Returns an empty list when ``path`` is missing or not a file.
    """
    if path is None or not path.is_file():
        return []
    out: list[WeatherSample] = []
    for line in _read_log(path).splitlines():
        m = WEATHER_LINE.search(line)
        if not m:
            continue
        out.append(
            WeatherSample(
                float(m.group(1)),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5),
            )
        )
    return out


def load_dome_events(path: Path | None) -> list[tuple[float, str]]:
    """
    Parse dome state changes from the scheduler log.

    Returns ``(ut_decimal, state)`` tuples where ``state`` is lowercased
    (e.g. ``open``, ``closed``). Consecutive duplicate states are collapsed.
    """
    if path is None or not path.is_file():
        return []
    events: list[tuple[float, str]] = []
    last: str | None = None
    for line in _read_log(path).splitlines():
        m = DOME_LINE.search(line)
        if not m:
            continue
        state = m.group(2).lower()
        if state != last:
            events.append((float(m.group(1)), state))
            last = state
    return events


def night_anchor_ut(
    dome: list[tuple[float, str]],
    exposure_ut: list[float],
) -> float:
    """
    Return the evening-side UT hour that starts the observing night.

    Used as the reference for mapping post-midnight times onto a continuous
    timeline via :func:`to_night_ut`.
    """
    for ut, st in dome:
        if st == "open":
            return ut
    if not exposure_ut:
        return 12.0
    uts = exposure_ut
    if max(uts) - min(uts) > 12.0:
        evening = [u for u in uts if u >= 12.0]
        if evening:
            return min(evening)
    return min(uts)


def to_night_ut(ut: float, anchor: float) -> float:
    """
    Map a clock UT hour onto the continuous night timeline.

    Times more than 2 h before ``anchor`` are treated as after local midnight
    and receive +24 h so they sort after evening exposures.
    """
    if ut < anchor - 2.0:
        return ut + 24.0
    return ut


def display_ut(night_ut: float) -> float:
    """Map continuous night UT back to 0–24 h for human-readable report lines."""
    return round(night_ut - 24.0, 6) if night_ut >= 24.0 else round(night_ut, 6)


def night_window(
    dome: list[tuple[float, str]],
    weather: list[WeatherSample],
    exposure_ut: list[float],
) -> tuple[float, float, float] | None:
    """
    Compute the observing window on the continuous night timeline.

    Returns ``(night_start, night_end, anchor)`` or None when dome and
    exposure data are insufficient to bound the night.
    """
    anchor = night_anchor_ut(dome, exposure_ut)
    starts: list[float] = []
    ends: list[float] = []
    for ut, st in dome:
        nu = to_night_ut(ut, anchor)
        if st == "open":
            starts.append(nu)
        elif st in ("closed", "close"):
            ends.append(nu)
    for ut in exposure_ut:
        nu = to_night_ut(ut, anchor)
        starts.append(nu)
        ends.append(nu)
    if not starts or not ends:
        return None
    return min(starts), max(ends), anchor


def grid_ut(start: float, end: float) -> list[float]:
    """
    Generate 30-minute grid times between ``start`` and ``end`` (night timeline).

    Grid points are aligned to :data:`GRID_STEP` (0.5 h).
    """
    t = math.floor(start / GRID_STEP) * GRID_STEP
    if t < start:
        t += GRID_STEP
    times = []
    while t <= end + 1e-9:
        times.append(round(t, 6))
        t += GRID_STEP
    return times


def nearest_on_night(
    night_ut: float,
    samples: list[WeatherSample],
    anchor: float,
    max_delta: float,
) -> WeatherSample | None:
    """
    Return the closest weather sample to ``night_ut`` within ``max_delta`` hours.

    Comparison uses the continuous night timeline (:func:`to_night_ut`).
    """
    best, best_d = None, max_delta + 1.0
    for s in samples:
        d = abs(to_night_ut(s.ut, anchor) - night_ut)
        if d <= max_delta and d < best_d:
            best, best_d = s, d
    return best
