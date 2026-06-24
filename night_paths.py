#!/usr/bin/env python3
"""Resolve obsplan / log.obs / scheduler log paths for one UT night."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from practice_config import (
    DIMM_LOG,
    DOME_DAEMON_LOG,
    GET_UT_DATE,
    LIVE_DATA_ROOTS,
    OBSPLAN_ROOT,
    OBSPLAN_ROOTS,
    PRACTICE_DOME_DAEMON_LOG,
    PRACTICE_NIGHTS,
    PRACTICE_ROOT,
    SEEING_LOG,
)


@dataclass
class NightPaths:
    date: str
    obsplan: Path
    log_obs: Path
    scheduler_log: Path | None
    dome_daemon_log: Path | None
    seeing_log: Path | None
    source: str


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _fallback_ut_date() -> str:
    """Match observer bin/get_ut_date when that script is unavailable."""
    now_local = datetime.now()
    if now_local.hour < 8:
        return now_local.strftime("%Y%m%d")
    d_local = now_local.strftime("%Y%m%d")
    d_ut = datetime.utcnow().strftime("%Y%m%d")
    if d_ut == d_local:
        return (now_local.date() + timedelta(days=1)).strftime("%Y%m%d")
    return d_ut


def get_default_ut_date() -> str:
    try:
        if _is_file(GET_UT_DATE):
            r = subprocess.run([str(GET_UT_DATE)], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().split()[-1]
    except OSError:
        pass
    return _fallback_ut_date()


def discover_practice_nights() -> list[str]:
    nights = []
    if not _is_dir(PRACTICE_ROOT):
        return nights
    try:
        entries = sorted(PRACTICE_ROOT.iterdir())
    except OSError:
        return nights
    for d in entries:
        if not _is_dir(d) or len(d.name) != 8 or not d.name.isdigit():
            continue
        obs = d / f"{d.name}.obsplan"
        log_obs = d / "logs" / "log.obs"
        if _is_file(obs) and _is_file(log_obs):
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
    seeing: Path | None,
    source: str,
) -> NightPaths:
    log_dir = log_obs.parent
    for candidate in (log_dir / "dimm.logs", DIMM_LOG, log_dir / "seeing.logs", seeing):
        if candidate and _is_file(candidate):
            night_dimm = candidate
            break
    else:
        night_dimm = seeing
    return NightPaths(
        date,
        obsplan,
        log_obs,
        sched if _is_file(sched) else None,
        daemon if daemon and _is_file(daemon) else None,
        night_dimm,
        source,
    )


def _practice_paths(date: str) -> NightPaths | None:
    night_dir = PRACTICE_ROOT / date
    obsplan = night_dir / f"{date}.obsplan"
    log_obs = night_dir / "logs" / "log.obs"
    if not _is_file(obsplan) or not _is_file(log_obs):
        return None
    return _night_paths(
        date, obsplan, log_obs, night_dir / "logs" / f"{date}.log", PRACTICE_DOME_DAEMON_LOG, None, "practice"
    )


def live_data_root() -> Path:
    for root in LIVE_DATA_ROOTS:
        if not _is_dir(root):
            continue
        try:
            if any(p.is_dir() and len(p.name) == 8 and p.name.isdigit() for p in root.iterdir()):
                return root
        except OSError:
            continue
    return LIVE_DATA_ROOTS[0]


def _obsplan_candidates(date: str, data_root: Path) -> list[Path]:
    names = [data_root / date / f"{date}.obsplan"]
    names.extend(obs_root / date / f"{date}.obsplan" for obs_root in OBSPLAN_ROOTS)
    return names


def discover_live_nights() -> list[str]:
    nights: list[str] = []
    for data_root in LIVE_DATA_ROOTS:
        if not _is_dir(data_root):
            continue
        try:
            entries = sorted(data_root.iterdir())
        except OSError:
            continue
        for d in entries:
            if not _is_dir(d) or len(d.name) != 8 or not d.name.isdigit():
                continue
            date = d.name
            log_obs = d / "logs" / "log.obs"
            if not _is_file(log_obs):
                continue
            if any(_is_file(p) for p in _obsplan_candidates(date, data_root)):
                nights.append(date)
    return sorted(set(nights))


def _live_paths(date: str) -> NightPaths | None:
    for data_root in LIVE_DATA_ROOTS:
        live_dir = data_root / date / "logs"
        log_obs = live_dir / "log.obs"
        if not _is_file(log_obs):
            continue
        for obsplan in _obsplan_candidates(date, data_root):
            if not _is_file(obsplan):
                continue
            return _night_paths(
                date, obsplan, log_obs, live_dir / f"{date}.log", DOME_DAEMON_LOG, DIMM_LOG, "live"
            )
    return None


def diagnose_live_night(date: str) -> str:
    """Human-readable checklist of what exists for a UT night (for error messages)."""
    lines = [f"night {date}:"]
    for data_root in LIVE_DATA_ROOTS:
        night_dir = data_root / date
        log_obs = night_dir / "logs" / "log.obs"
        sched = night_dir / "logs" / f"{date}.log"
        lines.append(f"  data tree {data_root}:")
        lines.append(f"    {night_dir}/  {'exists' if _is_dir(night_dir) else 'MISSING'}")
        lines.append(f"    {log_obs}  {'OK' if _is_file(log_obs) else 'MISSING (required)'}")
        lines.append(f"    {sched}  {'OK' if _is_file(sched) else 'missing (dome/weather need this)'}")
    lines.append("  obsplan (need one):")
    seen: set[str] = set()
    for data_root in LIVE_DATA_ROOTS:
        for obsplan in _obsplan_candidates(date, data_root):
            key = str(obsplan)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"    {obsplan}  {'OK' if _is_file(obsplan) else 'MISSING'}")
    return "\n".join(lines)


def resolve_night_paths(date: str, *, allow_practice_fallback: bool = True) -> NightPaths:
    paths = _live_paths(date)
    if paths is not None:
        return paths

    if not allow_practice_fallback:
        raise FileNotFoundError(
            f"no live logs for {date} under {LIVE_DATA_ROOTS} "
            f"with obsplan under {OBSPLAN_ROOTS}\n"
            f"{diagnose_live_night(date)}"
        )

    paths = _practice_paths(date)
    if paths:
        return paths
    raise FileNotFoundError(
        f"no logs for night {date}. Expected live data or "
        f"{PRACTICE_ROOT}/{date}/ with obsplan and logs/log.obs"
    )
