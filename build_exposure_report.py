#!/usr/bin/env python3
"""Observing and calibration exposure tables from log.obs."""

from __future__ import annotations

import re
from pathlib import Path

from seeing_samples import dimm_for_exposure, load_dimm_samples
from weather_samples import (
    load_dome_events,
    load_scheduler_weather,
    nearest_on_night,
    night_anchor_ut,
    to_night_ut,
)

FITS_RE = re.compile(r"(?<!\d)(\d{8})(\d{6})([a-zA-Z])?(?!\d)")
EXPOSURE_TOL = 10.0 / 60.0


def _fits_token(line: str) -> str | None:
    m = FITS_RE.search(line)
    if not m:
        return None
    suffix = m.group(3) or ""
    return f"{m.group(1)}{m.group(2)}{suffix}"


def _fits_ut_hours(token: str) -> float | None:
    m = FITS_RE.search(token)
    if not m:
        return None
    t = m.group(2)
    return int(t[:2]) + int(t[2:4]) / 60.0 + int(t[4:6]) / 3600.0


def _is_observing(shutter: str) -> bool:
    """Y/S = science; N/E/D/etc. = calibration (per obsplan and log.obs conventions)."""
    return shutter.upper() in ("Y", "S")


def _parse_line(line: str) -> dict | None:
    parts = line.split()
    if len(parts) < 8:
        return None
    fits = _fits_token(line)
    if not fits:
        return None
    ut = _fits_ut_hours(fits)
    if ut is None:
        return None
    shutter = parts[2]
    tag = line.split("#", 1)[1].strip() if "#" in line else ""
    return {
        "ut": ut,
        "ra": float(parts[0]),
        "dec": float(parts[1]),
        "shutter": shutter,
        "observing": _is_observing(shutter),
        "fits": re.sub(r"[a-zA-Z]$", "", fits),
        "tag": tag,
    }


def exposure_ut_list(log_obs: Path) -> list[float]:
    uts = []
    for line in log_obs.read_text().splitlines():
        row = _parse_line(line.strip())
        if row:
            uts.append(row["ut"])
    return uts


def _exposure_table(
    title: str,
    rows: list[dict],
    weather,
    dimm_samples,
    anchor: float,
) -> list[str]:
    lines = [title, f"  {'UT(h)':>6}  {'tag':<20}  {'RA':>7}  {'Dec':>7}  "
             f"{'Temp':>4}  {'RH%':>3}  {'Wind':>4}  {'Dir':>4}  {'DIMM':>4}  file"]
    for r in rows:
        night_ut = to_night_ut(r["ut"], anchor)
        w = nearest_on_night(night_ut, weather, anchor, EXPOSURE_TOL)
        dimm = dimm_for_exposure(night_ut, anchor, dimm_samples)
        if w:
            wx = f"{w.temp:>4}  {w.humid:>3}  {w.wind:>4}  {w.wind_dir:>4}"
        else:
            wx = " n/a  n/a  n/a  n/a"
        tag = (r["tag"][:18] + "..") if len(r["tag"]) > 20 else r["tag"]
        lines.append(
            f"  {r['ut']:6.3f}  {tag:<20}  {r['ra']:7.2f}  {r['dec']:7.2f}  "
            f"{wx}  {dimm:>4}  {r['fits']}"
        )
    return lines


def build_exposure_section(
    log_obs: Path,
    scheduler_log: Path | None,
    *,
    night_date: str | None = None,
    dimm_log: Path | None = None,
) -> str:
    lines = ["=== Exposures ===", f"  log.obs: {log_obs}", "  RA in hours, Dec in degrees"]
    weather = load_scheduler_weather(scheduler_log)
    dimm_samples = load_dimm_samples(dimm_log, night_date) if night_date and dimm_log else []
    if dimm_log:
        lines.append(f"  dimm.logs: {dimm_log} ({len(dimm_samples)} samples for night)")
    else:
        lines.append("  dimm.logs: (not found — DIMM column will show n/a)")

    rows = []
    for line in log_obs.read_text().splitlines():
        row = _parse_line(line.strip())
        if row:
            rows.append(row)

    if not rows:
        lines += ["  (no exposures)", ""]
        return "\n".join(lines) + "\n"

    dome = load_dome_events(scheduler_log)
    anchor = night_anchor_ut(dome, [r["ut"] for r in rows])
    rows.sort(key=lambda r: to_night_ut(r["ut"], anchor))

    obs = [r for r in rows if r["observing"]]
    cal = [r for r in rows if not r["observing"]]

    lines.append("")
    if obs:
        lines += _exposure_table(f"  Observing ({len(obs)})", obs, weather, dimm_samples, anchor)
    else:
        lines.append("  Observing (0)")

    lines.append("")
    if cal:
        lines += _exposure_table(f"  Calibration ({len(cal)})", cal, weather, dimm_samples, anchor)
    else:
        lines.append("  Calibration (0)")

    lines.append("")
    return "\n".join(lines) + "\n"
