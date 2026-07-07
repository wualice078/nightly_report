#!/usr/bin/env python3
"""Dome open/close timeline: questctl (manual) → scheduler → dome_daemon (safety)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dome_daemon import (
    count_daemon_closes_on_night,
    daemon_close_note,
    find_night_close_from_daemon,
)
from questctl_log import count_questctl_closes_on_night, find_night_close_from_questctl
from weather_samples import load_dome_events, night_anchor_ut, to_night_ut


@dataclass(frozen=True)
class DomeSummary:
    first_open: float | None
    last_close: float | None
    total_open_h: float
    intervals: list[tuple[float, float]]
    still_open: bool
    open_since: float | None
    last_close_source: str | None = None  # "questctl" | "scheduler" | "dome_daemon"
    close_utc: datetime | None = None
    close_note: str | None = None
    daemon_checked: bool = False
    daemon_closes_on_night: int = 0
    questctl_checked: bool = False
    questctl_closes_on_night: int = 0


def _interval_hours(t0: float, t1: float, anchor: float) -> float:
    return to_night_ut(t1, anchor) - to_night_ut(t0, anchor)


def _total_interval_hours(intervals: list[tuple[float, float]], anchor: float) -> float:
    return sum(_interval_hours(t0, t1, anchor) for t0, t1 in intervals)


def _set_close(
    *,
    first_open: float | None,
    open_ut: float | None,
    intervals: list[tuple[float, float]],
    close_ut: float,
    anchor: float,
    source: str,
    close_utc: datetime | None,
    close_note: str | None,
) -> DomeSummary:
    """Apply a resolved close time (overrides scheduler close when still open or more exact)."""
    ivals = list(intervals)
    if open_ut is not None:
        ivals.append((open_ut, close_ut))
    elif ivals:
        t0, _t1 = ivals[-1]
        ivals[-1] = (t0, close_ut)
    elif first_open is not None:
        ivals = [(first_open, close_ut)]

    total_h = _total_interval_hours(ivals, anchor)
    return DomeSummary(
        first_open=first_open,
        last_close=close_ut,
        total_open_h=total_h,
        intervals=ivals,
        still_open=False,
        open_since=None,
        last_close_source=source,
        close_utc=close_utc,
        close_note=close_note,
    )


def _is_end_of_night_close(close_ut: float, exposure_ut: list[float], anchor: float) -> bool:
    """True if close_ut is plausibly end-of-night (after last exposure, not a startup blip)."""
    if not exposure_ut:
        return True
    last_exp = max(to_night_ut(u, anchor) for u in exposure_ut)
    return to_night_ut(close_ut, anchor) >= last_exp - 0.25


def dome_summary(
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    questctl_log_dir: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> DomeSummary | None:
    events = load_dome_events(scheduler_log)
    if not events and not dome_daemon_log and not questctl_log_dir:
        return None

    exposure_ut = exposure_ut or []
    anchor = night_anchor_ut(events, exposure_ut)

    first_open: float | None = None
    scheduler_close: float | None = None
    open_ut: float | None = None
    intervals: list[tuple[float, float]] = []
    total_h = 0.0

    for ut, state in events:
        if state == "open":
            if first_open is None:
                first_open = ut
            open_ut = ut
        elif state in ("closed", "close"):
            scheduler_close = ut
            if open_ut is not None:
                intervals.append((open_ut, ut))
                total_h += _interval_hours(open_ut, ut, anchor)
                open_ut = None

    still_open = open_ut is not None
    end_close = scheduler_close
    if end_close is not None and exposure_ut and not _is_end_of_night_close(end_close, exposure_ut, anchor):
        end_close = None
        still_open = True
        if open_ut is None and first_open is not None:
            open_ut = first_open

    daemon_checked = False
    daemon_closes_on_night = 0
    questctl_checked = False
    questctl_closes_on_night = 0

    summary = DomeSummary(
        first_open=first_open,
        last_close=end_close,
        total_open_h=total_h,
        intervals=intervals,
        still_open=still_open,
        open_since=open_ut,
        last_close_source="scheduler" if end_close is not None else None,
        daemon_checked=daemon_checked,
        daemon_closes_on_night=daemon_closes_on_night,
        questctl_checked=questctl_checked,
        questctl_closes_on_night=questctl_closes_on_night,
    )

    if first_open is None or not night_date:
        if first_open is None and not intervals and not still_open and scheduler_close is None:
            return None
        return summary

    # 1) questctl CLOSE_CODE — usual manual end-of-night (exact unix timestamp)
    if questctl_log_dir:
        questctl_checked = questctl_log_dir.is_dir()
        if questctl_checked:
            questctl_closes_on_night = count_questctl_closes_on_night(questctl_log_dir, night_date)
        found = find_night_close_from_questctl(
            questctl_log_dir,
            night_date,
            first_open,
            exposure_ut,
            events,
        )
        if found:
            close_ut, close_utc_dt = found
            resolved = _set_close(
                first_open=first_open,
                open_ut=open_ut,
                intervals=intervals,
                close_ut=close_ut,
                anchor=anchor,
                source="questctl",
                close_utc=close_utc_dt,
                close_note="manual end-of-night (questctl CLOSE_CODE / closedome)",
            )
            return DomeSummary(
                **{
                    **resolved.__dict__,
                    "daemon_checked": daemon_checked,
                    "daemon_closes_on_night": daemon_closes_on_night,
                    "questctl_checked": questctl_checked,
                    "questctl_closes_on_night": questctl_closes_on_night,
                }
            )

    # 2) scheduler dome : closed (when TCS status was polled, after last exposure)
    if (
        scheduler_close is not None
        and not still_open
        and _is_end_of_night_close(scheduler_close, exposure_ut, anchor)
    ):
        return DomeSummary(
            first_open=first_open,
            last_close=scheduler_close,
            total_open_h=total_h,
            intervals=intervals,
            still_open=False,
            open_since=None,
            last_close_source="scheduler",
            daemon_checked=daemon_checked,
            daemon_closes_on_night=daemon_closes_on_night,
            questctl_checked=questctl_checked,
            questctl_closes_on_night=questctl_closes_on_night,
        )

    # 3) dome_daemon — weather/safety guard (uncommon)
    if dome_daemon_log:
        daemon_checked = dome_daemon_log.is_file()
        if daemon_checked:
            daemon_closes_on_night = count_daemon_closes_on_night(dome_daemon_log, night_date)
        found = find_night_close_from_daemon(
            dome_daemon_log,
            night_date,
            first_open,
            exposure_ut,
            events,
        )
        if found:
            close_ut, close_utc_dt = found
            resolved = _set_close(
                first_open=first_open,
                open_ut=open_ut,
                intervals=intervals,
                close_ut=close_ut,
                anchor=anchor,
                source="dome_daemon",
                close_utc=close_utc_dt,
                close_note=daemon_close_note(dome_daemon_log, close_utc_dt),
            )
            return DomeSummary(
                **{
                    **resolved.__dict__,
                    "daemon_checked": daemon_checked,
                    "daemon_closes_on_night": daemon_closes_on_night,
                    "questctl_checked": questctl_checked,
                    "questctl_closes_on_night": questctl_closes_on_night,
                }
            )

    return DomeSummary(
        first_open=first_open,
        last_close=scheduler_close,
        total_open_h=total_h,
        intervals=intervals,
        still_open=still_open,
        open_since=open_ut,
        last_close_source="scheduler" if scheduler_close is not None else None,
        daemon_checked=daemon_checked,
        daemon_closes_on_night=daemon_closes_on_night,
        questctl_checked=questctl_checked,
        questctl_closes_on_night=questctl_closes_on_night,
    )


def _format_utc(dt: datetime) -> str:
    u = dt.astimezone(timezone.utc)
    return u.strftime("%Y-%m-%d %H:%M:%S UTC")


def _resolved_close_lines(summary: DomeSummary) -> list[str]:
    if summary.last_close is None:
        return []
    lines = [
        f"  ** close time (from {summary.last_close_source}): UT {summary.last_close:.5f} h"
    ]
    if summary.close_note:
        lines.append(f"     {summary.close_note}")
    if summary.close_utc is not None:
        lines.append(f"     {_format_utc(summary.close_utc)}")
    return lines


def build_dome_section(
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    questctl_log_dir: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> str:
    lines = ["=== Dome ===", "  UT in hours"]
    events = load_dome_events(scheduler_log)
    summary = dome_summary(
        scheduler_log,
        night_date=night_date,
        dome_daemon_log=dome_daemon_log,
        questctl_log_dir=questctl_log_dir,
        exposure_ut=exposure_ut,
    )

    if not events and summary is None:
        lines += ["  (no dome status in scheduler log)", ""]
        return "\n".join(lines) + "\n"

    if questctl_log_dir and questctl_log_dir.is_dir():
        lines.append(f"  questctl logs: {questctl_log_dir}/questctl.*.log  (primary close time)")
    if scheduler_log:
        lines.append(f"  scheduler log: {scheduler_log}")
    if dome_daemon_log and dome_daemon_log.is_file():
        lines.append(f"  dome_daemon log: {dome_daemon_log}  (weather/safety fallback)")

    if events:
        lines.append(f"  {'#':>2}  {'UT(h)':>9}  event")
        for i, (ut, state) in enumerate(events, 1):
            lines.append(f"  {i:02d}  {ut:9.5f}  {state.upper()}")

    if summary:
        lines.extend(_resolved_close_lines(summary))

    if summary and summary.intervals:
        anchor = night_anchor_ut(events, exposure_ut or [])
        lines.append("  intervals (open):")
        for i, (t0, t1) in enumerate(summary.intervals, 1):
            dur = _interval_hours(t0, t1, anchor)
            lines.append(f"    {i:02d}  {t0:9.5f} - {t1:9.5f}  ({dur:.3f} h)")
    elif summary and summary.still_open and summary.open_since is not None:
        parts = [f"still open from UT {summary.open_since:.5f} h"]
        if summary.questctl_checked and summary.questctl_closes_on_night == 0:
            parts.append("no questctl CLOSE_CODE")
        elif summary.questctl_checked:
            parts.append(f"questctl {summary.questctl_closes_on_night} CLOSE signal(s) unmatched")
        if summary.daemon_checked and summary.daemon_closes_on_night == 0:
            parts.append("no dome_daemon close")
        elif summary.daemon_checked:
            parts.append(f"dome_daemon {summary.daemon_closes_on_night} unmatched")
        lines.append(f"  {'; '.join(parts)}")
    if summary and summary.total_open_h > 0:
        lines.append(f"  total open: {summary.total_open_h:.3f} h ({summary.total_open_h * 60:.1f} min)")
    elif summary and not summary.intervals and not summary.still_open:
        lines.append("  note: no complete open/close interval in log")

    lines.append("")
    return "\n".join(lines) + "\n"
