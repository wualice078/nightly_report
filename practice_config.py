#!/usr/bin/env python3
"""Settings for nightly reports (NUC production + Northwestern practice)."""

from __future__ import annotations

import os
from pathlib import Path

# Email recipient for morning cron
MORNING_REPORT_EMAIL = "wualice078@berkeley.edu"


def _live_only() -> bool:
    v = os.environ.get("LS4_LIVE_ONLY")
    if v is not None:
        return v not in ("0", "false", "False", "no", "NO")
    return True


MORNING_REPORT_LIVE_ONLY = _live_only()

HOME = Path.home()
OBSERVER_ROOT = Path(os.environ.get("LS4_OBSERVER_ROOT", "/home/observer"))

PRACTICE_ROOT = Path(
    os.environ.get("LS4_PRACTICE_ROOT", str(OBSERVER_ROOT / "2026_recent_logs/obslogs_and_plans"))
)
PRACTICE_NIGHTS: list[str] | None = None


def _unique_paths(paths: list[Path]) -> list[Path]:
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
OBSPLAN_ROOT = OBSPLAN_ROOTS[0]

DOME_DAEMON_LOG = Path(
    os.environ.get("LS4_DOME_DAEMON_LOG", str(OBSERVER_ROOT / "logs/dome_daemon.log"))
)
# On the mountain, LS4_ROOT is /home/observer; questctl/dimm logs live in ~/logs/.
_LS4_ROOT = Path(os.environ.get("LS4_ROOT", str(OBSERVER_ROOT)))
QUESTCTL_LOG_DIR = Path(
    os.environ.get("LS4_QUESTCTL_LOG_DIR", str(OBSERVER_ROOT / "logs"))
)
DIMM_LOG = Path(os.environ.get("LS4_DIMM_LOG", str(_LS4_ROOT / "logs/dimm.logs")))
ESO_DIMM_URL = os.environ.get(
    "LS4_ESO_DIMM_URL",
    "https://www.ls.eso.org/lasilla/dimm/dimm.last",
)
PRACTICE_DOME_DAEMON_LOG = OBSERVER_ROOT / "recent_logs/logfiles/dome_daemon.log"
PRACTICE_QUESTCTL_LOG_DIR = OBSERVER_ROOT / "recent_logs/logfiles"
GET_UT_DATE = Path(os.environ.get("LS4_GET_UT_DATE", str(OBSERVER_ROOT / "bin/get_ut_date")))

# NUC: ~/nightly_report/   Cron: 0 7 * * * ~/nightly_report/send_morning_report.sh
