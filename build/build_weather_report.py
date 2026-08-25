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
    night_window,
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
    window = night_window(load_dome_events(scheduler_log), weather, exposure_ut or [])

    if not weather or window is None:
        lines += ["  (no weather data for this night)", ""]
        return "\n".join(lines) + "\n"

    start, end, anchor = window
    lines.append(
        f"  window: {display_ut(start):.3f} - {display_ut(end):.3f} h"
    )
    if scheduler_log:
        lines.append(f"  source: {scheduler_log}")
    lines.append(f"  {'UT(h)':>7}  {'Temp':>4}  {'RH%':>4}  {'Wind':>4}  {'Dir':>4}")

    for t in grid_ut(start, end):
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
