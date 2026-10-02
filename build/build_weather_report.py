#!/usr/bin/env python3
"""
Weather section: 30-minute UT grid over the observing window.

Samples Temp, RH%, wind speed, and wind direction from the scheduler log at
:class:`lib.weather_samples.GRID_STEP` intervals (30 minutes). The grid spans
from first dome open / first exposure through last close / last exposure.
"""

from __future__ import annotations

from pathlib import Path

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
    **_kwargs,
) -> str:
    """
    Build the ``=== Weather (30 min UT) ===`` report section.

    ``exposure_ut`` extends the weather window when dome events alone are sparse.
    Extra keyword arguments are ignored (call-site compatibility with other builders).
    """
    lines = ["=== Weather (30 min UT) ===", "  UT in hours"]
    weather = load_scheduler_weather(scheduler_log)
    dome = load_dome_events(scheduler_log)
    window = night_window(dome, weather, exposure_ut or [])

    if not weather:
        lines += ["  (no weather data for this night)", ""]
        return "\n".join(lines) + "\n"

    if window is None:
        # No open-to-close or exposure span (e.g. dome stayed shut for weather):
        # cover every logged weather sample so the reason is visible.
        anchor = night_anchor_ut(dome, exposure_ut or [])
        night_uts = [to_night_ut(s.ut, anchor) for s in weather]
        start, end = min(night_uts), max(night_uts)
        lines.append("  (no observing window — showing all logged weather)")
    else:
        start, end, anchor = window
    lines.append(
        f"  window: {display_ut(start):.3f} - {display_ut(end):.3f} h"
    )
    if scheduler_log:
        lines.append(f"  source: {scheduler_log}")
    lines.append(f"  {'UT(h)':>7}  {'Temp':>4}  {'RH%':>4}  {'Wind':>4}  {'Dir':>4}")

    grid = grid_ut(start, end)
    if not grid:
        # Window shorter than one grid step: list the raw samples inside it.
        for s in weather:
            if start - 1e-6 <= to_night_ut(s.ut, anchor) <= end + 1e-6:
                lines.append(
                    f"  {s.ut:7.3f}  {s.temp:>4}  {s.humid:>4}  {s.wind:>4}  {s.wind_dir:>4}"
                )
    for t in grid:
        s: WeatherSample | None = nearest_on_night(t, weather, anchor, GRID_STEP)
        label = display_ut(t)
        if s:
            lines.append(
                f"  {label:7.3f}  {s.temp:>4}  {s.humid:>4}  {s.wind:>4}  {s.wind_dir:>4}"
            )
        else:
            lines.append(f"  {label:7.3f}   n/a   n/a   n/a   n/a")

    lines.append("")
    return "\n".join(lines) + "\n"
