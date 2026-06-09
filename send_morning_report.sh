#!/bin/bash
# Morning cron wrapper — logs output for debugging.
DIR=/home/observer/nightly_report
LOG="$DIR/reports/cron_morning.log"
mkdir -p "$DIR/reports"
{
  echo "=== $(date -Iseconds) ==="
  /home/ls4/observer_venv/bin/python3 "$DIR/send_morning_report.py"
} >> "$LOG" 2>&1
