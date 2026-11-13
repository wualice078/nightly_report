#!/usr/bin/env python3
"""
Weather section: 30-minute UT grid over the dome-open window.

Samples Temp, RH%, wind speed, and wind direction from the scheduler log at
:class:`lib.weather_samples.GRID_STEP` intervals (30 minutes). The grid spans
dome open → dome close when those times are known (same resolution as the
summary timeline); otherwise it falls back to scheduler dome events and
exposures.
"""

from __future__ import annotations

from pathlib import Path

from lib.text_table import format_table
from lib.weather_samples import (
    GRID_STEP,
    WeatherSample,
    display_ut,
    grid_ut,
    load_dome_events,
    load_scheduler_weather,
    nearest_on_night,
    night_anchor_ut,
    night_window,
    to_night_ut,
)


def build_weather_section(
    scheduler_log: Path | None,
    *,
    exposure_ut: list[float] | None = None,
    dome_open: float | None = None,
    dome_close: float | None = None,
    **_kwargs,
) -> str:
    """
    Build the ``=== Weather (30 min UT) ===`` report section.

    ``dome_open`` / ``dome_close`` set the preferred grid window (resolved
    summary times). ``exposure_ut`` is only used when those are incomplete.
    Extra keyword arguments are ignored (call-site compatibility).
    """
    lines = ["=== Weather (30 min UT) ===", "  UT in hours"]
    weather = load_scheduler_weather(scheduler_log)
    dome = load_dome_events(scheduler_log)
    window = night_window(
        dome,
        weather,
        exposure_ut or [],
        dome_open=dome_open,
        dome_close=dome_close,
    )

    if not weather:
        lines += ["  (no weather data for this night)", ""]
        return "\n".join(lines) + "\n"

    if window is None:
        # No open-to-close or exposure span (e.g. dome stayed shut for weather):
        # cover every logged weather sample so the reason is visible.
        anchor_events = list(dome)
        if dome_open is not None:
            anchor_events = [(dome_open, "open"), *anchor_events]
        anchor = night_anchor_ut(anchor_events, exposure_ut or [])
        night_uts = [to_night_ut(s.ut, anchor) for s in weather]
        start, end = min(night_uts), max(night_uts)
        lines.append("  (no dome open/close window — showing all logged weather)")
    else:
        start, end, anchor = window
    lines.append(
        f"  window: {display_ut(start):.3f} - {display_ut(end):.3f} h"
    )
    if scheduler_log:
        lines.append(f"  source: {scheduler_log}")

    headers = ["UT(h)", "Temp", "RH%", "Wind", "Dir"]
    table_rows: list[list[str]] = []
    grid = grid_ut(start, end)
    if not grid:
        # Window shorter than one grid step: list the raw samples inside it.
        for s in weather:
            if start - 1e-6 <= to_night_ut(s.ut, anchor) <= end + 1e-6:
                table_rows.append(
                    [f"{s.ut:.3f}", s.temp, s.humid, s.wind, s.wind_dir]
                )
    for t in grid:
        s: WeatherSample | None = nearest_on_night(t, weather, anchor, GRID_STEP)
        label = f"{display_ut(t):.3f}"
        if s:
            table_rows.append([label, s.temp, s.humid, s.wind, s.wind_dir])
        else:
            table_rows.append([label, "n/a", "n/a", "n/a", "n/a"])

    lines.extend(format_table(headers, table_rows))
    lines.append("")
    return "\n".join(lines) + "\n"
