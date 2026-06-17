#!/usr/bin/env python3
"""Resolve obsplan / log.obs / scheduler log paths for one UT night."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from practice_config import (
    DOME_DAEMON_LOG,
    GET_UT_DATE,
    LIVE_DATA_ROOTS,
    OBSPLAN_ROOT,
    PRACTICE_DOME_DAEMON_LOG,
    PRACTICE_NIGHTS,
    PRACTICE_ROOT,
)


@dataclass
class NightPaths:
    date: str
    obsplan: Path
    log_obs: Path
    scheduler_log: Path | None
    dome_daemon_log: Path | None
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


def _night_paths(
    date: str,
    obsplan: Path,
    log_obs: Path,
    sched: Path,
    daemon: Path | None,
    source: str,
) -> NightPaths:
    return NightPaths(
        date,
        obsplan,
        log_obs,
        sched if sched.is_file() else None,
        daemon if daemon and daemon.is_file() else None,
        source,
    )


def _practice_paths(date: str) -> NightPaths | None:
    night_dir = PRACTICE_ROOT / date
    obsplan = night_dir / f"{date}.obsplan"
    log_obs = night_dir / "logs" / "log.obs"
    if not obsplan.is_file() or not log_obs.is_file():
        return None
    return _night_paths(
        date, obsplan, log_obs, night_dir / "logs" / f"{date}.log", PRACTICE_DOME_DAEMON_LOG, "practice"
    )


def live_data_root() -> Path:
    """Prefer a live data tree that actually has night directories."""
    for root in LIVE_DATA_ROOTS:
        if not root.is_dir():
            continue
        try:
            if any(p.is_dir() and len(p.name) == 8 and p.name.isdigit() for p in root.iterdir()):
                return root
        except OSError:
            continue
    return LIVE_DATA_ROOTS[0]


def discover_live_nights() -> list[str]:
    """UT nights with obsplan + log.obs under the live data tree."""
    root = live_data_root()
    nights: list[str] = []
    if not root.is_dir():
        return nights
    for d in sorted(root.iterdir()):
        if not d.is_dir() or len(d.name) != 8 or not d.name.isdigit():
            continue
        date = d.name
        obsplan = OBSPLAN_ROOT / date / f"{date}.obsplan"
        log_obs = d / "logs" / "log.obs"
        if obsplan.is_file() and log_obs.is_file():
            nights.append(date)
    return nights


def _live_paths(date: str) -> NightPaths | None:
    root = live_data_root()
    live_dir = root / date / "logs"
    obsplan = OBSPLAN_ROOT / date / f"{date}.obsplan"
    log_obs = live_dir / "log.obs"
    if not obsplan.is_file() or not log_obs.is_file():
        return None
    return _night_paths(date, obsplan, log_obs, live_dir / f"{date}.log", DOME_DAEMON_LOG, "live")


def resolve_night_paths(date: str, *, allow_practice_fallback: bool = True) -> NightPaths:
    paths = _live_paths(date)
    if paths is not None:
        return paths

    if not allow_practice_fallback:
        root = live_data_root()
        raise FileNotFoundError(
            f"no live logs for {date}: {OBSPLAN_ROOT / date / f'{date}.obsplan'}, "
            f"{root / date / 'logs' / 'log.obs'}"
        )

    paths = _practice_paths(date)
    if paths:
        return paths
    raise FileNotFoundError(
        f"no logs for night {date}. Expected live data or "
        f"{PRACTICE_ROOT}/{date}/ with obsplan and logs/log.obs"
    )
