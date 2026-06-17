#!/usr/bin/env python3
"""Dome open/close timeline from scheduler log (+ dome_daemon.log fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dome_daemon import find_night_close_from_daemon
from weather_samples import load_dome_events, night_anchor_ut, to_night_ut


@dataclass(frozen=True)
class DomeSummary:
    first_open: float | None
    last_close: float | None
    total_open_h: float
    intervals: list[tuple[float, float]]
    still_open: bool
    open_since: float | None
    last_close_source: str | None = None  # "scheduler" | "dome_daemon"
    daemon_close_utc: datetime | None = None


def _interval_hours(t0: float, t1: float, anchor: float) -> float:
    return to_night_ut(t1, anchor) - to_night_ut(t0, anchor)


def _apply_close(
    summary: DomeSummary,
    close_ut: float,
    *,
    source: str,
    anchor: float,
    daemon_close_utc: datetime | None = None,
) -> DomeSummary:
    intervals = list(summary.intervals)
    total_h = summary.total_open_h
    open_ut = summary.open_since

    if open_ut is not None:
        intervals.append((open_ut, close_ut))
        total_h += _interval_hours(open_ut, close_ut, anchor)
        open_ut = None

    return DomeSummary(
        first_open=summary.first_open,
        last_close=close_ut,
        total_open_h=total_h,
        intervals=intervals,
        still_open=False,
        open_since=open_ut,
        last_close_source=source,
        daemon_close_utc=daemon_close_utc,
    )


def dome_summary(
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> DomeSummary | None:
    events = load_dome_events(scheduler_log)
    if not events and not dome_daemon_log:
        return None

    exposure_ut = exposure_ut or []
    anchor = night_anchor_ut(events, exposure_ut)

    first_open: float | None = None
    last_close: float | None = None
    last_close_source: str | None = None
    daemon_close_utc: datetime | None = None
    open_ut: float | None = None
    total_h = 0.0
    intervals: list[tuple[float, float]] = []

    for ut, state in events:
        if state == "open":
            if first_open is None:
                first_open = ut
            open_ut = ut
        elif state in ("closed", "close"):
            last_close = ut
            last_close_source = "scheduler"
            if open_ut is not None:
                intervals.append((open_ut, ut))
                total_h += _interval_hours(open_ut, ut, anchor)
                open_ut = None

    summary = DomeSummary(
        first_open=first_open,
        last_close=last_close,
        total_open_h=total_h,
        intervals=intervals,
        still_open=open_ut is not None,
        open_since=open_ut,
        last_close_source=last_close_source,
        daemon_close_utc=daemon_close_utc,
    )

    need_daemon = (
        first_open is not None
        and (last_close is None or summary.still_open)
        and night_date
        and dome_daemon_log
    )
    if need_daemon:
        found = find_night_close_from_daemon(
            dome_daemon_log,
            night_date,
            first_open,
            exposure_ut or [],
            events,
        )
        if found:
            close_ut, close_utc = found
            summary = _apply_close(
                summary,
                close_ut,
                source="dome_daemon",
                anchor=anchor,
                daemon_close_utc=close_utc,
            )

    if first_open is None and not intervals and not summary.still_open and last_close is None:
        return None
    return summary


def _format_utc(dt: datetime) -> str:
    u = dt.astimezone(timezone.utc)
    return u.strftime("%Y-%m-%d %H:%M:%S UTC")


def build_dome_section(
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> str:
    lines = ["=== Dome ===", "  UT in hours"]
    events = load_dome_events(scheduler_log)
    summary = dome_summary(
        scheduler_log,
        night_date=night_date,
        dome_daemon_log=dome_daemon_log,
        exposure_ut=exposure_ut,
    )

    if not events and summary is None:
        lines += ["  (no dome status in scheduler log)", ""]
        return "\n".join(lines) + "\n"

    if scheduler_log:
        lines.append(f"  scheduler log: {scheduler_log}")
    if dome_daemon_log and dome_daemon_log.is_file():
        lines.append(f"  dome_daemon log: {dome_daemon_log}")

    if events:
        lines.append(f"  {'#':>2}  {'UT(h)':>9}  event")
        for i, (ut, state) in enumerate(events, 1):
            lines.append(f"  {i:02d}  {ut:9.5f}  {state.upper()}")

    if summary and summary.last_close_source == "dome_daemon" and summary.last_close is not None:
        lines.append(
            f"  ** dome_daemon close (scheduler log had no close): "
            f"UT {summary.last_close:.5f} h"
        )
        if summary.daemon_close_utc is not None:
            lines.append(f"     {_format_utc(summary.daemon_close_utc)}")

    if summary and summary.intervals:
        anchor = night_anchor_ut(events, exposure_ut or [])
        lines.append("  intervals (open):")
        for i, (t0, t1) in enumerate(summary.intervals, 1):
            dur = _interval_hours(t0, t1, anchor)
            lines.append(f"    {i:02d}  {t0:9.5f} - {t1:9.5f}  ({dur:.3f} h)")
    elif summary and summary.still_open and summary.open_since is not None:
        lines.append(f"  still open from UT {summary.open_since:.5f} h (no close recorded)")
    if summary and summary.total_open_h > 0:
        lines.append(f"  total open: {summary.total_open_h:.3f} h ({summary.total_open_h * 60:.1f} min)")
    elif summary and not summary.intervals and not summary.still_open:
        lines.append("  note: no complete open/close interval in log")

    lines.append("")
    return "\n".join(lines) + "\n"
