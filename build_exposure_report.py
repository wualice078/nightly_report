#!/usr/bin/env python3
"""Observing and calibration exposure tables from log.obs."""

from __future__ import annotations

import re
from pathlib import Path

from weather_samples import load_scheduler_weather, nearest

FITS_RE = re.compile(r"(\d{8})(\d{6})s")
EXPOSURE_TOL = 10.0 / 60.0


def _fits_ut_hours(token: str) -> float | None:
    m = FITS_RE.search(token)
    if not m:
        return None
    t = m.group(2)
    return int(t[:2]) + int(t[2:4]) / 60.0 + int(t[4:6]) / 3600.0


def _is_observing(shutter: str) -> bool:
    return shutter.lower() in ("s", "y")


def _parse_line(line: str) -> dict | None:
    parts = line.split()
    if len(parts) < 8:
        return None
    fits = next((p for p in parts if FITS_RE.search(p)), None)
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
        "fits": fits.rstrip("s"),
        "tag": tag,
    }


def exposure_ut_list(log_obs: Path) -> list[float]:
    uts = []
    for line in log_obs.read_text().splitlines():
        row = _parse_line(line.strip())
        if row:
            uts.append(row["ut"])
    return uts


def _exposure_table(title: str, rows: list[dict], weather) -> list[str]:
    lines = [title, f"  {'UT(h)':>6}  {'tag':<20}  {'RA':>7}  {'Dec':>7}  "
             f"{'Temp':>4}  {'RH%':>3}  {'Wind':>4}  {'Dir':>4}  {'DIMM':>4}  file"]
    for r in rows:
        w = nearest(r["ut"], weather, EXPOSURE_TOL)
        dimm = w.seeing if w and w.seeing else "n/a"
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


def build_exposure_section(log_obs: Path, scheduler_log: Path | None) -> str:
    lines = ["=== Exposures ===", f"  log.obs: {log_obs}", "  RA in hours, Dec in degrees"]
    weather = load_scheduler_weather(scheduler_log)

    rows = []
    for line in log_obs.read_text().splitlines():
        row = _parse_line(line.strip())
        if row:
            rows.append(row)

    if not rows:
        lines += ["  (no exposures)", ""]
        return "\n".join(lines) + "\n"

    obs = [r for r in rows if r["observing"]]
    cal = [r for r in rows if not r["observing"]]

    lines.append("")
    if obs:
        lines += _exposure_table(f"  Observing ({len(obs)})", obs, weather)
    else:
        lines.append("  Observing (0)")

    lines.append("")
    if cal:
        lines += _exposure_table(f"  Calibration ({len(cal)})", cal, weather)
    else:
        lines.append("  Calibration (0)")

    lines.append("")
    return "\n".join(lines) + "\n"
