#!/usr/bin/env python3
"""Weather section: 30-minute UT grid over the full observing window."""

from __future__ import annotations

from pathlib import Path

from weather_samples import (
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
        s: WeatherSample | None = nearest_on_night(t, weather, anchor, GRID_STEP / 2)
        label = display_ut(t)
        if s:
            lines.append(
                f"  {label:7.3f}  {s.temp:>4}  {s.humid:>4}  {s.wind:>4}  {s.wind_dir:>4}"
            )
        else:
            lines.append(f"  {label:7.3f}   n/a   n/a   n/a   n/a")

    lines.append("")
    return "\n".join(lines) + "\n"
