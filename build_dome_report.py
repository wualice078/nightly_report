#!/usr/bin/env python3
"""Dome open/close timeline from scheduler log."""

from __future__ import annotations

from pathlib import Path

from weather_samples import load_dome_events


def build_dome_section(scheduler_log: Path | None) -> str:
    lines = ["=== Dome ===", "  UT in hours"]
    events = load_dome_events(scheduler_log)
    if not events:
        lines += ["  (no dome status in scheduler log)", ""]
        return "\n".join(lines) + "\n"

    lines.append(f"  log: {scheduler_log}")
    lines.append(f"  {'#':>2}  {'UT(h)':>9}  event")
    for i, (ut, state) in enumerate(events, 1):
        lines.append(f"  {i:02d}  {ut:9.5f}  {state.upper()}")

    open_ut = None
    total_h = 0.0
    intervals: list[tuple[float, float]] = []
    for ut, state in events:
        if state == "open":
            open_ut = ut
        elif state in ("closed", "close") and open_ut is not None:
            intervals.append((open_ut, ut))
            total_h += ut - open_ut
            open_ut = None

    if intervals:
        lines.append("  intervals (open):")
        for i, (t0, t1) in enumerate(intervals, 1):
            dur = t1 - t0
            lines.append(f"    {i:02d}  {t0:9.5f} - {t1:9.5f}  ({dur:.3f} h)")
    if open_ut is not None:
        lines.append(f"  still open from UT {open_ut:.5f} h (no close in log)")
    if total_h > 0:
        lines.append(f"  total open: {total_h:.3f} h ({total_h * 60:.1f} min)")
    elif open_ut is None and not intervals:
        lines.append("  note: no complete open/close interval in log")

    lines.append("")
    return "\n".join(lines) + "\n"
