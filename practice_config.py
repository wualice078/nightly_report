#!/usr/bin/env python3
"""Settings for nightly reports (NUC production + Northwestern practice)."""

from __future__ import annotations

import os
from pathlib import Path

# Email recipient for morning cron
MORNING_REPORT_EMAIL = "wualice078@berkeley.edu"

# Production (mountain): live observer data only.  Practice (Northwestern): LS4_LIVE_ONLY=0
def _live_only() -> bool:
    v = os.environ.get("LS4_LIVE_ONLY")
    if v is not None:
        return v not in ("0", "false", "False", "no", "NO")
    return True


MORNING_REPORT_LIVE_ONLY = _live_only()

# Observer data (read-only on NUC via NFS). Override: export LS4_OBSERVER_ROOT=...
OBSERVER_ROOT = Path(os.environ.get("LS4_OBSERVER_ROOT", "/home/observer"))

PRACTICE_ROOT = Path(
    os.environ.get("LS4_PRACTICE_ROOT", str(OBSERVER_ROOT / "2026_recent_logs/obslogs_and_plans"))
)
PRACTICE_NIGHTS: list[str] | None = None

LIVE_DATA_ROOTS = [OBSERVER_ROOT / "data", Path("/data/observer")]
OBSPLAN_ROOT = OBSERVER_ROOT / "obsplans"
DOME_DAEMON_LOG = OBSERVER_ROOT / "logs/dome_daemon.log"
PRACTICE_DOME_DAEMON_LOG = OBSERVER_ROOT / "recent_logs/logfiles/dome_daemon.log"
GET_UT_DATE = Path(os.environ.get("LS4_GET_UT_DATE", str(OBSERVER_ROOT / "bin/get_ut_date")))

# NUC install:  ~/nightly_report/
# Cron:         0 7 * * * /home/ls4/nightly_report/send_morning_report.sh
# Reports:      ~/nightly_report/reports/report_YYYYMMDD.txt
