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
    log_dir: Path
    obsplan: Path | None
    log_obs: Path | None
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


def _first_file(candidates) -> Path | None:
    """Return the first existing file among ``candidates``, or None."""
    for p in candidates:
        if _is_file(p):
            return p
    return None


def _practice_night_files(date: str) -> tuple[Path, Path | None, Path | None, Path | None] | None:
    """
    Locate the log dir, obsplan, log.obs, and scheduler log for a practice night.

    Archives come in two layouts:

    * ``night/log.obs`` (``~/all_logs``)
    * ``night/logs/log.obs`` (``~/2026_recent_logs/obslogs_and_plans``)

    Any of the three files may be missing; returns None only when all are.
    """
    night_dir = PRACTICE_ROOT / date
    obsplan_only = None
    for log_dir in (night_dir / "logs", night_dir):
        log_obs = _first_file([log_dir / "log.obs"])
        sched = _first_file([log_dir / f"{date}.log"])
        obsplan = _first_file([night_dir / f"{date}.obsplan", log_dir / f"{date}.obsplan"])
        if log_obs or sched:
            return log_dir, obsplan, log_obs, sched
        if obsplan and obsplan_only is None:
            obsplan_only = (log_dir, obsplan, None, None)
    return obsplan_only


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
    log_dir: Path,
    obsplan: Path | None,
    log_obs: Path | None,
    sched: Path | None,
    daemon: Path | None,
    questctl_dir: Path | None,
    source: str,
) -> NightPaths:
    """Build a :class:`NightPaths`, omitting optional paths that do not exist."""
    return NightPaths(
        date,
        log_dir,
        obsplan,
        log_obs,
        sched,
        daemon if daemon and _is_file(daemon) else None,
        questctl_dir if questctl_dir and _is_dir(questctl_dir) else None,
        _resolve_dimm_log(log_dir),
        source,
    )


def _practice_paths(date: str) -> NightPaths | None:
    """Resolve paths from the practice archive for ``date``, or None."""
    found = _practice_night_files(date)
    if not found:
        return None
    log_dir, obsplan, log_obs, sched = found
    return _night_paths(
        date, log_dir, obsplan, log_obs, sched,
        PRACTICE_DOME_DAEMON_LOG, PRACTICE_QUESTCTL_LOG_DIR, "practice",
    )


def _obsplan_candidates(date: str, data_root: Path) -> list[Path]:
    """Possible obsplan locations for a night (data tree and obsplan roots)."""
    names = [data_root / date / f"{date}.obsplan"]
    names.extend(obs_root / date / f"{date}.obsplan" for obs_root in OBSPLAN_ROOTS)
    return names


def discover_live_nights() -> list[str]:
    """List UT dates with any live night input (log.obs, scheduler log, or obsplan)."""
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
            if _live_files(d.name, data_root):
                nights.append(d.name)
    return sorted(set(nights))


def _live_files(date: str, data_root: Path) -> tuple[Path | None, Path | None, Path | None] | None:
    """Return ``(obsplan, log_obs, sched)`` under one data root, or None if all are missing."""
    live_dir = data_root / date / "logs"
    log_obs = _first_file([live_dir / "log.obs"])
    sched = _first_file([live_dir / f"{date}.log"])
    obsplan = _first_file(_obsplan_candidates(date, data_root))
    if log_obs or sched or obsplan:
        return obsplan, log_obs, sched
    return None


def _live_paths(date: str) -> NightPaths | None:
    """
    Resolve paths from live mountain data trees for ``date``, or None.

    A data root with log.obs or a scheduler log wins over one that only
    matched an obsplan (obsplan roots are shared by every data root).
    """
    hits = []
    for data_root in LIVE_DATA_ROOTS:
        found = _live_files(date, data_root)
        if found:
            hits.append((data_root, found))
    if not hits:
        return None
    data_root, (obsplan, log_obs, sched) = next(
        (h for h in hits if h[1][1] or h[1][2]), hits[0]
    )
    return _night_paths(
        date, data_root / date / "logs", obsplan, log_obs, sched,
        DOME_DAEMON_LOG, QUESTCTL_LOG_DIR, "live",
    )


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
        lines.append(f"    {log_obs}  {'OK' if _is_file(log_obs) else 'MISSING'}")
        lines.append(f"    {sched}  {'OK' if _is_file(sched) else 'MISSING'}")
    lines.append("  obsplan:")
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
    ``PRACTICE_ROOT``. A night resolves when any of log.obs, the scheduler log,
    or the obsplan exists; the rest are None. Raises :exc:`FileNotFoundError`
    with diagnostics when none of them exist.
    """
    paths = _live_paths(date)
    if paths is not None:
        return paths

    if not allow_practice_fallback:
        raise FileNotFoundError(
            f"no log.obs, scheduler log, or obsplan for {date} under {LIVE_DATA_ROOTS} "
            f"or {OBSPLAN_ROOTS}\n"
            f"{diagnose_live_night(date)}"
        )

    paths = _practice_paths(date)
    if paths:
        return paths
    raise FileNotFoundError(
        f"no logs for night {date}. Expected live data or "
        f"{PRACTICE_ROOT}/{date}/ with log.obs, {date}.log, or {date}.obsplan"
    )
