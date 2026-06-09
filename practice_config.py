#!/usr/bin/env python3
"""
Practice vs production settings for nightly reports.

MOUNTAIN (production):
  - Set MORNING_REPORT_LIVE_ONLY = True (no practice fallback).
  - Change MORNING_REPORT_EMAIL to Lead Observer lookup when ready.

CRON (7 AM server local time):
  0 7 * * * /home/observer/nightly_report/send_morning_report.sh

Uses observer_venv Python (system /usr/bin/python3 is too old).
"""

from __future__ import annotations

from pathlib import Path

# Morning email recipient (you for now; Lead Observer from sheet later)
MORNING_REPORT_EMAIL = "wualice078@berkeley.edu"

# False = use practice archive when live logs missing (good for testing)
# True  = production: DATA MISSING email if no live logs
MORNING_REPORT_LIVE_ONLY = True

# Practice archive — only used when live logs are missing
PRACTICE_ROOT = Path("/home/observer/2026_recent_logs/obslogs_and_plans")
PRACTICE_NIGHTS: list[str] | None = None

# Live paths (mountain)
LIVE_DATA_ROOT = Path("/data/observer")
OBSPLAN_ROOT = Path("/home/observer/obsplans")
WEATHER_LOG = Path("/home/observer/logs/weather.logs")
