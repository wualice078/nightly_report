#!/usr/bin/env python3
"""
Shared weather/dome parsing for nightly report sections.

Weather today: scheduler log (YYYYMMDD.log) Temp/Humid/Wnd.
DIMM seeing: not in logs yet — add ingest on mountain when ASM/ESO
data is available; SEEING_LINE regex is ready for scheduler lines.
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
SEEING_LINE = re.compile(
    r"(?:seeing|DIMM|dimm)\s*:\s*([\d.]+)",
    re.IGNORECASE,
)

GRID_STEP = 0.5  # 30 minutes in decimal UT hours


def _read_log(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class WeatherSample:
    ut: float
    temp: str
    humid: str
    wind: str
    wind_dir: str
    seeing: str | None = None


def load_scheduler_weather(path: Path | None) -> list[WeatherSample]:
    if path is None or not path.is_file():
        return []
    out: list[WeatherSample] = []
    for line in _read_log(path).splitlines():
        m = WEATHER_LINE.search(line)
        if not m:
            continue
        sm = SEEING_LINE.search(line)
        out.append(
            WeatherSample(
                float(m.group(1)),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5),
                sm.group(1) if sm else None,
            )
        )
    return out


def load_dome_events(path: Path | None) -> list[tuple[float, str]]:
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


def night_window(
    dome: list[tuple[float, str]],
    weather: list[WeatherSample],
    exposure_ut: list[float],
) -> tuple[float, float] | None:
    starts, ends = [], []
    for ut, st in dome:
        if st == "open":
            starts.append(ut)
        elif st in ("closed", "close"):
            ends.append(ut)
    if exposure_ut:
        starts.append(min(exposure_ut))
        ends.append(max(exposure_ut))
    if weather:
        starts.append(weather[0].ut)
        ends.append(weather[-1].ut)
    if not starts or not ends:
        return None
    return min(starts), max(ends)


def grid_ut(start: float, end: float) -> list[float]:
    t = math.floor(start / GRID_STEP) * GRID_STEP
    if t < start:
        t += GRID_STEP
    times = []
    while t <= end + 1e-9:
        times.append(round(t, 6))
        t += GRID_STEP
    return times


def nearest(ut: float, samples: list[WeatherSample], max_delta: float) -> WeatherSample | None:
    best, best_d = None, max_delta + 1.0
    for s in samples:
        d = abs(s.ut - ut)
        if d <= max_delta and d < best_d:
            best, best_d = s, d
    return best
