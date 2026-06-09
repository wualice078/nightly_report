#!/usr/bin/env python3
"""Cron entry: build and email last night's report to MORNING_REPORT_EMAIL."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE))

from practice_config import MORNING_REPORT_EMAIL, MORNING_REPORT_LIVE_ONLY


def main() -> int:
    cmd = [
        sys.executable,
        str(PACKAGE / "send_report_email.py"),
        "--to",
        MORNING_REPORT_EMAIL,
    ]
    if MORNING_REPORT_LIVE_ONLY:
        cmd.append("--no-practice-fallback")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
