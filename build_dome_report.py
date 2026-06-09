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
    for ut, state in events:
        if state == "open":
            open_ut = ut
        elif state in ("closed", "close") and open_ut is not None:
            total_h += ut - open_ut
            open_ut = None

    if open_ut is not None:
        lines.append("  note: no dome close in log (run may have ended early)")
    elif total_h > 0:
        lines.append(f"  total open: {total_h:.3f} h ({total_h * 60:.1f} min)")

    lines.append("")
    return "\n".join(lines) + "\n"
