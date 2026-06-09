#!/usr/bin/env python3
"""Resolve obsplan / log.obs / scheduler log paths for one UT night."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from practice_config import LIVE_DATA_ROOT, OBSPLAN_ROOT, PRACTICE_ROOT

ROOT = Path("/home/observer")
GET_UT_DATE = ROOT / "bin/get_ut_date"


@dataclass
class NightPaths:
    date: str
    obsplan: Path
    log_obs: Path
    scheduler_log: Path | None
    source: str


def get_default_ut_date() -> str:
    if GET_UT_DATE.is_file():
        r = subprocess.run([str(GET_UT_DATE)], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split()[-1]
    return datetime.utcnow().strftime("%Y%m%d")


def discover_practice_nights() -> list[str]:
    """Nights under PRACTICE_ROOT that have obsplan + log.obs."""
    nights = []
    if not PRACTICE_ROOT.is_dir():
        return nights
    for d in sorted(PRACTICE_ROOT.iterdir()):
        if not d.is_dir() or len(d.name) != 8 or not d.name.isdigit():
            continue
        obs = d / f"{d.name}.obsplan"
        log_obs = d / "logs" / "log.obs"
        if obs.is_file() and log_obs.is_file():
            nights.append(d.name)
    return nights


def practice_night_list() -> list[str]:
    if PRACTICE_NIGHTS:
        return list(PRACTICE_NIGHTS)
    return discover_practice_nights()


def _practice_paths(date: str) -> NightPaths | None:
    night_dir = PRACTICE_ROOT / date
    obsplan = night_dir / f"{date}.obsplan"
    log_obs = night_dir / "logs" / "log.obs"
    sched = night_dir / "logs" / f"{date}.log"
    if not obsplan.is_file() or not log_obs.is_file():
        return None
    return NightPaths(
        date,
        obsplan,
        log_obs,
        sched if sched.is_file() else None,
        "practice",
    )


def resolve_night_paths(date: str, *, allow_practice_fallback: bool = True) -> NightPaths:
    live_dir = LIVE_DATA_ROOT / date / "logs"
    obsplan = OBSPLAN_ROOT / date / f"{date}.obsplan"
    log_obs = live_dir / "log.obs"
    sched = live_dir / f"{date}.log"
    if log_obs.is_file() and obsplan.is_file():
        return NightPaths(date, obsplan, log_obs, sched if sched.is_file() else None, "live")

    if not allow_practice_fallback:
        raise FileNotFoundError(f"no live logs for {date}: {obsplan}, {log_obs}")

    paths = _practice_paths(date)
    if paths:
        return paths
    raise FileNotFoundError(
        f"no logs for night {date}. Expected live data or "
        f"{PRACTICE_ROOT}/{date}/ with obsplan and logs/log.obs"
    )
