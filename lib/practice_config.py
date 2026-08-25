#!/usr/bin/env python3
"""
Configuration and path defaults for LS4 nightly reports.

This module centralizes environment-variable overrides used on the mountain
NUC (``observer@ls4-workstn``) and on Northwestern practice machines. Paths
here are consumed by :mod:`lib.night_paths` when resolving obsplan, ``log.obs``,
scheduler logs, questctl logs, dome_daemon logs, and DIMM samples for one UT night.

Environment variables (see README for full list):

    LS4_OBSERVER_ROOT, LS4_ROOT, LS4_DATA_ROOT, LS4_OBSPLAN_ROOT,
    LS4_QUESTCTL_LOG_DIR, LS4_DOME_DAEMON_LOG, LS4_DIMM_LOG,
    LS4_GET_UT_DATE, LS4_PRACTICE_ROOT, LS4_LIVE_ONLY
"""

from __future__ import annotations

import os
from pathlib import Path

# Email recipient for morning cron
MORNING_REPORT_EMAIL = "wualice078@berkeley.edu"


def _live_only() -> bool:
    """Return True when morning cron should use live data only (no practice archive)."""
    v = os.environ.get("LS4_LIVE_ONLY")
    if v is not None:
        return v not in ("0", "false", "False", "no", "NO")
    return True


MORNING_REPORT_LIVE_ONLY = _live_only()

HOME = Path.home()
OBSERVER_ROOT = Path(os.environ.get("LS4_OBSERVER_ROOT", "/home/observer"))

# Archived nights for testing: ~/all_logs (Oct 2025 onward).
# Older copy with a logs/ subdir per night: ~/2026_recent_logs/obslogs_and_plans
PRACTICE_ROOT = Path(
    os.environ.get("LS4_PRACTICE_ROOT", str(OBSERVER_ROOT / "all_logs"))
)
PRACTICE_NIGHTS: list[str] | None = None


def _unique_paths(paths: list[Path]) -> list[Path]:
    """Deduplicate path list while preserving order."""
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


# NUC: ls4 often reads ~/data, not /home/observer (permission denied). Override with LS4_DATA_ROOT.
LIVE_DATA_ROOTS = _unique_paths(
    [Path(p) for p in os.environ.get("LS4_DATA_ROOT", "").split(":") if p]
    + [
        HOME / "data",
        OBSERVER_ROOT / "data",
        Path("/data/observer"),
    ]
)

OBSPLAN_ROOTS = _unique_paths(
    [Path(p) for p in os.environ.get("LS4_OBSPLAN_ROOT", "").split(":") if p]
    + [
        HOME / "obsplans",
        OBSERVER_ROOT / "obsplans",
    ]
)

DOME_DAEMON_LOG = Path(
    os.environ.get("LS4_DOME_DAEMON_LOG", str(OBSERVER_ROOT / "logs/dome_daemon.log"))
)
# On the mountain, LS4_ROOT is /home/observer; questctl/dimm logs live in ~/logs/.
_LS4_ROOT = Path(os.environ.get("LS4_ROOT", str(OBSERVER_ROOT)))
QUESTCTL_LOG_DIR = Path(
    os.environ.get("LS4_QUESTCTL_LOG_DIR", str(OBSERVER_ROOT / "logs"))
)
DIMM_LOG = Path(os.environ.get("LS4_DIMM_LOG", str(_LS4_ROOT / "logs/dimm.logs")))
PRACTICE_DOME_DAEMON_LOG = OBSERVER_ROOT / "recent_logs/logfiles/dome_daemon.log"
PRACTICE_QUESTCTL_LOG_DIR = OBSERVER_ROOT / "recent_logs/logfiles"
GET_UT_DATE = Path(os.environ.get("LS4_GET_UT_DATE", str(OBSERVER_ROOT / "bin/get_ut_date")))

# NUC: ~/nightly_report/   Cron: 0 7 * * * ~/nightly_report/cron_morning.sh
