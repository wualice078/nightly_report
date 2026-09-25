#!/usr/bin/env python3
"""
Dome open/close timeline and close-time resolution for the nightly report.

Reads dome state changes from the scheduler log and resolves the authoritative
**last close** time using this priority:

    1. dome_daemon ``schmidt dome now closed`` (confirmed close)
    2. questctl shutter bit ``1→2→0`` (TCS status; ``2`` is opening/closing)
    3. questctl ``CLOSE_CODE`` (manual ``closedome``)
    4. scheduler ``dome : closed`` (after last exposure)

Public API:

    :class:`DomeSummary` — structured dome statistics for one night
    :func:`dome_summary` — compute summary from logs
    :func:`build_dome_section` — formatted ``=== Dome ===`` report text
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lib.dome_daemon import (
    belongs_to_ut_night,
    count_daemon_closes_on_night,
    daemon_close_note,
    find_night_close_from_daemon,
    load_dome_daemon_closes,
    utc_to_ut_decimal,
)
from lib.questctl_log import (
    count_questctl_bit_closes_on_night,
    count_questctl_closes_on_night,
    find_night_close_from_dome_bits,
    find_night_close_from_questctl,
    load_dome_bit_events_on_night,
    load_questctl_closes,
)
from lib.weather_samples import load_dome_events, night_anchor_ut, to_night_ut


@dataclass(frozen=True)
class DomeSummary:
    """
    Dome statistics for one UT observing night.

    ``last_close_source`` is one of ``questctl``, ``scheduler``, ``dome_daemon``,
    or None when no close was resolved. ``close_utc`` and ``close_note`` are set
    when the close came from questctl (shutter bit or CLOSE_CODE) or dome_daemon.
    """

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
    questctl_bit_closes_on_night: int = 0
    # (clock UT hours, action, source) — every logged shutter change, not just the slot
    actions: tuple[tuple[float, str, str], ...] = ()


def _interval_hours(t0: float, t1: float, anchor: float) -> float:
    """Duration in hours between two UT times on the continuous night timeline."""
    return to_night_ut(t1, anchor) - to_night_ut(t0, anchor)


def _total_interval_hours(intervals: list[tuple[float, float]], anchor: float) -> float:
    """Sum open-interval durations on the night timeline."""
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
    """
    Apply a resolved close time to dome state.

    Appends or extends the last open interval and marks the dome as closed.
    Used when questctl or dome_daemon overrides an incomplete scheduler timeline.
    """
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
    """
    Return True if ``close_ut`` plausibly marks end-of-night.

    Rejects early scheduler closes that occur before the last exposure (startup
    blips). Allows 15 minutes before last exposure.
    """
    if not exposure_ut:
        return True
    last_exp = max(to_night_ut(u, anchor) for u in exposure_ut)
    return to_night_ut(close_ut, anchor) >= last_exp - 0.25


_BIT_ACTION = {0: "CLOSED", 1: "OPEN", 2: "MOVING"}


def collect_dome_actions(
    scheduler_log: Path | None,
    *,
    night_date: str | None,
    dome_daemon_log: Path | None,
    questctl_log_dir: Path | None,
    exposure_ut: list[float],
) -> tuple[tuple[float, str, str], ...]:
    """
    Every dome state change on the night, from all logs, chronological.

    ``action`` is OPEN / CLOSED / MOVING / CLOSE_CODE. ``source`` names the log.
    Multiple opens and closes in one UT night are all kept.
    """
    sched = load_dome_events(scheduler_log)
    exposure_ut = exposure_ut or []
    anchor = night_anchor_ut(sched, exposure_ut)
    rows: list[tuple[float, float, str, str]] = []  # night_ut, clock_ut, action, source

    for ut, state in sched:
        action = "OPEN" if state == "open" else "CLOSED"
        rows.append((to_night_ut(ut, anchor), ut, action, "scheduler"))

    if night_date and questctl_log_dir:
        for dt, bit in load_dome_bit_events_on_night(questctl_log_dir, night_date):
            ut = utc_to_ut_decimal(dt)
            action = _BIT_ACTION.get(bit, f"BIT{bit}")
            rows.append((to_night_ut(ut, anchor), ut, action, "questctl bits"))
        for dt in load_questctl_closes(questctl_log_dir, night_date):
            ut = utc_to_ut_decimal(dt)
            rows.append((to_night_ut(ut, anchor), ut, "CLOSE_CODE", "questctl"))

    if night_date and dome_daemon_log:
        for dt in load_dome_daemon_closes(dome_daemon_log):
            if not belongs_to_ut_night(dt, night_date):
                continue
            ut = utc_to_ut_decimal(dt)
            rows.append((to_night_ut(ut, anchor), ut, "CLOSED", "dome_daemon"))

    rows.sort(key=lambda r: (r[0], r[3], r[2]))
    return tuple((clock, action, source) for _n, clock, action, source in rows)


def _observing_slot_open(
    opens: list[float],
    exposure_ut: list[float],
    anchor: float,
) -> float | None:
    """
    Open time for the observing slot (not a short test).

    If there are exposures, use the last OPEN at or before the first exposure.
    """
    if not opens:
        return None
    if not exposure_ut:
        return min(opens, key=lambda u: to_night_ut(u, anchor))
    first_e = min(to_night_ut(u, anchor) for u in exposure_ut)
    before = [u for u in opens if to_night_ut(u, anchor) <= first_e + 0.25]
    if before:
        return max(before, key=lambda u: to_night_ut(u, anchor))
    return min(opens, key=lambda u: to_night_ut(u, anchor))


def dome_summary(
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    questctl_log_dir: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> DomeSummary | None:
    """
    Compute dome statistics for one night from available logs.

    Parses scheduler dome events first, then optionally refines ``last_close``
    using dome_daemon then questctl when ``night_date`` is provided.

    Returns None when no dome-related inputs exist.
    """
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
    questctl_bit_closes_on_night = 0
    actions: tuple[tuple[float, str, str], ...] = ()

    def _with_counts(resolved: DomeSummary) -> DomeSummary:
        return DomeSummary(
            **{
                **resolved.__dict__,
                "daemon_checked": daemon_checked,
                "daemon_closes_on_night": daemon_closes_on_night,
                "questctl_checked": questctl_checked,
                "questctl_closes_on_night": questctl_closes_on_night,
                "questctl_bit_closes_on_night": questctl_bit_closes_on_night,
                "actions": actions,
            }
        )

    if not night_date:
        if first_open is None and not intervals and not still_open and scheduler_close is None:
            return None
        return _with_counts(
            DomeSummary(
                first_open=first_open,
                last_close=end_close,
                total_open_h=total_h,
                intervals=intervals,
                still_open=still_open,
                open_since=open_ut,
                last_close_source="scheduler" if end_close is not None else None,
            )
        )

    actions = collect_dome_actions(
        scheduler_log,
        night_date=night_date,
        dome_daemon_log=dome_daemon_log,
        questctl_log_dir=questctl_log_dir,
        exposure_ut=exposure_ut,
    )
    if questctl_log_dir:
        questctl_checked = questctl_log_dir.is_dir()
        if questctl_checked:
            questctl_bit_closes_on_night = count_questctl_bit_closes_on_night(
                questctl_log_dir, night_date
            )
            questctl_closes_on_night = count_questctl_closes_on_night(questctl_log_dir, night_date)

    slot_open = _observing_slot_open(
        [ut for ut, act, _src in actions if act == "OPEN"],
        exposure_ut,
        anchor,
    )
    if slot_open is not None:
        first_open = slot_open
        if open_ut is None:
            open_ut = slot_open
            still_open = True
        anchor = night_anchor_ut(events + [(slot_open, "open")], exposure_ut)

    # 1) dome_daemon — confirmed closed (weather, sun-up, or operator CLOSE)
    if dome_daemon_log and first_open is not None:
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
            return _with_counts(
                _set_close(
                    first_open=first_open,
                    open_ut=open_ut,
                    intervals=intervals,
                    close_ut=close_ut,
                    anchor=anchor,
                    source="dome_daemon",
                    close_utc=close_utc_dt,
                    close_note=daemon_close_note(dome_daemon_log, close_utc_dt),
                )
            )

    if questctl_log_dir:
        # 2) TCS shutter bit 1→2→0 (questctl polling during stow)
        found = find_night_close_from_dome_bits(
            questctl_log_dir,
            night_date,
            first_open,
            exposure_ut,
            events,
        )
        if found:
            close_ut, close_utc_dt = found
            return _with_counts(
                _set_close(
                    first_open=first_open,
                    open_ut=open_ut,
                    intervals=intervals,
                    close_ut=close_ut,
                    anchor=anchor,
                    source="questctl",
                    close_utc=close_utc_dt,
                    close_note="questctl shutter 1→2→0 (TCS dome status; 2 = opening/closing)",
                )
            )

        # 3) CLOSE_CODE — manual closedome
        found = find_night_close_from_questctl(
            questctl_log_dir,
            night_date,
            first_open,
            exposure_ut,
            events,
        )
        if found:
            close_ut, close_utc_dt = found
            return _with_counts(
                _set_close(
                    first_open=first_open,
                    open_ut=open_ut,
                    intervals=intervals,
                    close_ut=close_ut,
                    anchor=anchor,
                    source="questctl",
                    close_utc=close_utc_dt,
                    close_note="manual end-of-night (questctl CLOSE_CODE / closedome)",
                )
            )

    if first_open is None and not intervals and not still_open and scheduler_close is None:
        return None

    # 4) scheduler dome : closed (when TCS status was polled, after last exposure)
    if (
        scheduler_close is not None
        and not still_open
        and _is_end_of_night_close(scheduler_close, exposure_ut, anchor)
    ):
        return _with_counts(
            DomeSummary(
                first_open=first_open,
                last_close=scheduler_close,
                total_open_h=total_h,
                intervals=intervals,
                still_open=False,
                open_since=None,
                last_close_source="scheduler",
            )
        )

    return _with_counts(
        DomeSummary(
            first_open=first_open,
            last_close=scheduler_close,
            total_open_h=total_h,
            intervals=intervals,
            still_open=still_open,
            open_since=open_ut,
            last_close_source="scheduler" if scheduler_close is not None else None,
        )
    )


def _format_utc(dt: datetime) -> str:
    """Format a datetime as ``YYYY-MM-DD HH:MM:SS UTC``."""
    u = dt.astimezone(timezone.utc)
    return u.strftime("%Y-%m-%d %H:%M:%S UTC")


def _resolved_close_lines(summary: DomeSummary) -> list[str]:
    """Format resolved close time, note, and UTC for the dome section."""
    if summary.last_close is None:
        return []
    lines = [
        f"  ** slot end (from {summary.last_close_source}): UT {summary.last_close:.5f} h"
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
    """
    Build the ``=== Dome ===`` report section.

    Lists every dome action from scheduler, questctl bits, CLOSE_CODE, and
    dome_daemon. The resolved close is the observing-slot end, not a short test.
    """
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

    if dome_daemon_log and dome_daemon_log.is_file():
        lines.append(f"  dome_daemon log: {dome_daemon_log}  (preferred close time)")
    if questctl_log_dir and questctl_log_dir.is_dir():
        lines.append(f"  questctl logs: {questctl_log_dir}/questctl.*.log  (shutter bits / CLOSE_CODE)")
    if scheduler_log:
        lines.append(f"  scheduler log: {scheduler_log}")

    if summary and summary.actions:
        lines.append("  all actions:")
        lines.append(f"  {'#':>2}  {'UT(h)':>9}  {'event':<10}  source")
        for i, (ut, action, source) in enumerate(summary.actions, 1):
            lines.append(f"  {i:02d}  {ut:9.5f}  {action:<10}  {source}")
    elif events:
        lines.append(f"  {'#':>2}  {'UT(h)':>9}  event")
        for i, (ut, state) in enumerate(events, 1):
            lines.append(f"  {i:02d}  {ut:9.5f}  {state.upper()}")

    if summary:
        lines.append("  observing slot:")
        if summary.first_open is not None:
            lines.append(f"    start  UT {summary.first_open:.5f} h")
        lines.extend(_resolved_close_lines(summary))

    if summary and summary.intervals:
        anchor = night_anchor_ut(events, exposure_ut or [])
        lines.append("  intervals (open):")
        for i, (t0, t1) in enumerate(summary.intervals, 1):
            dur = _interval_hours(t0, t1, anchor)
            lines.append(f"    {i:02d}  {t0:9.5f} - {t1:9.5f}  ({dur:.3f} h)")
    elif summary and summary.still_open and summary.open_since is not None:
        parts = [f"still open from UT {summary.open_since:.5f} h"]
        if summary.daemon_checked and summary.daemon_closes_on_night == 0:
            parts.append("no dome_daemon close")
        elif summary.daemon_checked:
            parts.append(f"dome_daemon {summary.daemon_closes_on_night} unmatched")
        if summary.questctl_checked and summary.questctl_bit_closes_on_night == 0:
            parts.append("no questctl shutter 1→0")
        elif summary.questctl_checked:
            parts.append(f"questctl {summary.questctl_bit_closes_on_night} shutter close(s) unmatched")
        if summary.questctl_checked and summary.questctl_closes_on_night == 0:
            parts.append("no CLOSE_CODE")
        elif summary.questctl_checked and summary.questctl_closes_on_night:
            parts.append(f"{summary.questctl_closes_on_night} CLOSE_CODE unmatched")
        lines.append(f"  {'; '.join(parts)}")
    if summary and summary.total_open_h > 0:
        lines.append(f"  total open: {summary.total_open_h:.3f} h ({summary.total_open_h * 60:.1f} min)")
    elif summary and not summary.intervals and not summary.still_open:
        lines.append("  note: no complete open/close interval in log")

    lines.append("")
    return "\n".join(lines) + "\n"
