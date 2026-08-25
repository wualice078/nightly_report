#!/usr/bin/env python3
"""
Resolve input file paths for one UT observing night.

Given a UT date label ``YYYYMMDD``, this module finds the obsplan, ``log.obs``,
scheduler log, and optional auxiliary logs (questctl, dome_daemon, DIMM).
It supports both **live** mountain data under ``~/data/YYYYMMDD/`` and **practice**
archives under ``PRACTICE_ROOT``.

Primary entry points:

    :func:`resolve_night_paths` — return a :class:`NightPaths` bundle or raise
    :func:`get_default_ut_date` — UT night label used when ``--date`` is omitted
    :func:`discover_live_nights` / :func:`practice_night_list` — batch builders
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from lib.practice_config import (
    DIMM_LOG,
    DOME_DAEMON_LOG,
    GET_UT_DATE,
    LIVE_DATA_ROOTS,
    OBSPLAN_ROOTS,
    PRACTICE_DOME_DAEMON_LOG,
    PRACTICE_QUESTCTL_LOG_DIR,
    PRACTICE_NIGHTS,
    PRACTICE_ROOT,
    QUESTCTL_LOG_DIR,
)


@dataclass
class NightPaths:
    """All input paths needed to build one night's report."""

    date: str
    obsplan: Path
    log_obs: Path
    scheduler_log: Path | None
    dome_daemon_log: Path | None
    questctl_log_dir: Path | None
    dimm_log: Path | None
    source: str  # "live" or "practice"


def _is_dir(path: Path) -> bool:
    """Return True if ``path`` is an existing directory (OSError-safe)."""
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_file(path: Path) -> bool:
    """Return True if ``path`` is an existing regular file (OSError-safe)."""
    try:
        return path.is_file()
    except OSError:
        return False


def _fallback_ut_date() -> str:
    """Approximate ``get_ut_date`` when the mountain script is unavailable."""
    now_local = datetime.now()
    if now_local.hour < 8:
        return now_local.strftime("%Y%m%d")
    d_local = now_local.strftime("%Y%m%d")
    d_ut = datetime.utcnow().strftime("%Y%m%d")
    if d_ut == d_local:
        return (now_local.date() + timedelta(days=1)).strftime("%Y%m%d")
    return d_ut


def get_default_ut_date() -> str:
    """
    Return the UT observing-night label for "tonight" or the most recent night.

    Calls ``GET_UT_DATE`` (``~/bin/get_ut_date`` on the mountain) when present;
    otherwise uses :func:`_fallback_ut_date`.
    """
    try:
        if _is_file(GET_UT_DATE):
            r = subprocess.run([str(GET_UT_DATE)], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().split()[-1]
    except OSError:
        pass
    return _fallback_ut_date()


def _practice_night_files(date: str) -> tuple[Path, Path, Path] | None:
    """
    Locate obsplan, log.obs, and scheduler log for an archived practice night.

    Archives come in two layouts:

    * ``night/log.obs`` (``~/all_logs``)
    * ``night/logs/log.obs`` (``~/2026_recent_logs/obslogs_and_plans``)
    """
    night_dir = PRACTICE_ROOT / date
    for log_dir in (night_dir / "logs", night_dir):
        log_obs = log_dir / "log.obs"
        if not _is_file(log_obs):
            continue
        for obsplan in (night_dir / f"{date}.obsplan", log_dir / f"{date}.obsplan"):
            if _is_file(obsplan):
                return obsplan, log_obs, log_dir / f"{date}.log"
    return None


def discover_practice_nights() -> list[str]:
    """Scan ``PRACTICE_ROOT`` for subdirectories that contain a complete night."""
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
        if _practice_night_files(d.name):
            nights.append(d.name)
    return nights


def practice_night_list() -> list[str]:
    """Return configured practice nights, or discover them under ``PRACTICE_ROOT``."""
    if PRACTICE_NIGHTS:
        return list(PRACTICE_NIGHTS)
    return discover_practice_nights()


def _resolve_dimm_log(log_dir: Path) -> Path | None:
    """Prefer archived ``dimm.logs`` in the night dir, else the live mountain file."""
    for candidate in (log_dir / "dimm.logs", DIMM_LOG):
        if _is_file(candidate):
            return candidate
    return None


def _night_paths(
    date: str,
    obsplan: Path,
    log_obs: Path,
    sched: Path,
    daemon: Path | None,
    questctl_dir: Path | None,
    source: str,
) -> NightPaths:
    """Build a :class:`NightPaths`, omitting optional paths that do not exist."""
    return NightPaths(
        date,
        obsplan,
        log_obs,
        sched if _is_file(sched) else None,
        daemon if daemon and _is_file(daemon) else None,
        questctl_dir if questctl_dir and _is_dir(questctl_dir) else None,
        _resolve_dimm_log(log_obs.parent),
        source,
    )


def _practice_paths(date: str) -> NightPaths | None:
    """Resolve paths from the practice archive for ``date``, or None."""
    found = _practice_night_files(date)
    if not found:
        return None
    obsplan, log_obs, sched = found
    return _night_paths(
        date, obsplan, log_obs, sched, PRACTICE_DOME_DAEMON_LOG, PRACTICE_QUESTCTL_LOG_DIR, "practice"
    )


def _obsplan_candidates(date: str, data_root: Path) -> list[Path]:
    """Possible obsplan locations for a night (data tree and obsplan roots)."""
    names = [data_root / date / f"{date}.obsplan"]
    names.extend(obs_root / date / f"{date}.obsplan" for obs_root in OBSPLAN_ROOTS)
    return names


def discover_live_nights() -> list[str]:
    """List UT dates with live ``log.obs`` and at least one obsplan under configured roots."""
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
    """Resolve paths from live mountain data trees for ``date``, or None."""
    for data_root in LIVE_DATA_ROOTS:
        live_dir = data_root / date / "logs"
        log_obs = live_dir / "log.obs"
        if not _is_file(log_obs):
            continue
        for obsplan in _obsplan_candidates(date, data_root):
            if not _is_file(obsplan):
                continue
            return _night_paths(
                date, obsplan, log_obs, live_dir / f"{date}.log", DOME_DAEMON_LOG, QUESTCTL_LOG_DIR, "live"
            )
    return None


def diagnose_live_night(date: str) -> str:
    """
    Human-readable checklist of expected live paths for ``date``.

    Used in :exc:`FileNotFoundError` messages when a night cannot be resolved.
    """
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
    """
    Resolve all input paths for UT night ``date``.

    Tries live data first. When ``allow_practice_fallback`` is True, falls back to
    ``PRACTICE_ROOT``. Raises :exc:`FileNotFoundError` with diagnostics when
    neither source has the required files.
    """
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
        f"{PRACTICE_ROOT}/{date}/ with obsplan and log.obs (in the night dir or logs/)"
    )
