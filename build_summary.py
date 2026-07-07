#!/usr/bin/env python3
"""Lead-observer summary: field completion and dome times."""

from __future__ import annotations

from pathlib import Path

from build_dome_report import dome_summary
from compare_obsplan_log import (
    field_counts,
    is_observing_field,
    parse_log_obs,
    parse_obsplan,
)


def _format_field_line(label: str, s: dict[str, int]) -> str:
    return (
        f"  {label}: {s['planned']} planned, "
        f"{s['complete']} complete, {s['partial']} partial, {s['not_observed']} not observed"
    )


def _format_ut(ut: float) -> str:
    h = int(ut)
    m = int((ut - h) * 60)
    s = round(((ut - h) * 60 - m) * 60)
    if s == 60:
        m += 1
        s = 0
    if m == 60:
        h += 1
        m = 0
    return f"{ut:.3f} h ({h:02d}:{m:02d}:{s:02d} UT)"


def _close_source_label(source: str | None, note: str | None) -> str:
    if source is None:
        return ""
    if note:
        return f" ({note})"
    if source == "dome_daemon":
        return " (from dome_daemon.log)"
    if source == "questctl":
        return " (from questctl log)"
    if source == "scheduler":
        return " (from scheduler log)"
    return ""


def build_summary_section(
    obsplan: Path,
    log_obs: Path,
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dome_daemon_log: Path | None = None,
    questctl_log_dir: Path | None = None,
    exposure_ut: list[float] | None = None,
) -> str:
    planned = parse_obsplan(obsplan)
    log_lines = parse_log_obs(log_obs)
    obs = field_counts([f for f in planned if is_observing_field(f)], log_lines)
    cal = field_counts([f for f in planned if not is_observing_field(f)], log_lines)

    lines = [
        "=== Night summary ===",
        _format_field_line("Observing fields", obs),
        f"    ({obs['complete'] + obs['partial']} with at least one exposure)",
        _format_field_line("Calibration fields", cal),
        f"    ({cal['complete'] + cal['partial']} with at least one exposure)",
        f"  Exposures in log: {len(log_lines)}",
    ]

    dome = dome_summary(
        scheduler_log,
        night_date=night_date,
        dome_daemon_log=dome_daemon_log,
        questctl_log_dir=questctl_log_dir,
        exposure_ut=exposure_ut,
    )
    if dome is None:
        lines.append("  Dome: (no scheduler log)")
    elif dome.first_open is None:
        lines.append("  Dome: no open/close events in log")
    else:
        lines.append(f"  Dome first open:  {_format_ut(dome.first_open)}")
        if dome.last_close is not None:
            lines.append(
                f"  Dome last close:  {_format_ut(dome.last_close)}"
                f"{_close_source_label(dome.last_close_source, dome.close_note)}"
            )
        elif dome.still_open:
            parts = ["scheduler log ended open"]
            if dome.daemon_checked and dome.daemon_closes_on_night == 0:
                parts.append("no dome_daemon close")
            elif dome.daemon_checked:
                parts.append(f"dome_daemon {dome.daemon_closes_on_night} unmatched")
            if dome.questctl_checked and dome.questctl_closes_on_night == 0:
                parts.append("no questctl CLOSE")
            elif dome.questctl_checked:
                parts.append(f"questctl {dome.questctl_closes_on_night} unmatched")
            lines.append(f"  Dome last close:  n/a ({'; '.join(parts)})")
        if dome.total_open_h > 0:
            lines.append(
                f"  Dome total open:  {dome.total_open_h:.3f} h ({dome.total_open_h * 60:.1f} min)"
            )
        elif dome.still_open and not dome.intervals:
            lines.append("  Dome total open:  n/a (no close recorded)")

    lines.append("")
    return "\n".join(lines) + "\n"
