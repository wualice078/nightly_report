#!/bin/bash
# Morning cron wrapper — logs output for debugging.
# Install on NUC: 0 7 * * * /home/ls4/nightly_report/send_morning_report.sh
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/reports/cron_morning.log"
PY="${LS4_PYTHON:-/home/ls4/code/observer_venv/bin/python3}"
if [ ! -x "$PY" ]; then
  PY=/home/ls4/observer_venv/bin/python3
fi
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi
export LS4_OBSERVER_ROOT="${LS4_OBSERVER_ROOT:-/home/observer}"
export LS4_LIVE_ONLY="${LS4_LIVE_ONLY:-1}"
mkdir -p "$DIR/reports"
{
  echo "=== $(date -Iseconds) ==="
  echo "package=$DIR observer_root=$LS4_OBSERVER_ROOT python=$PY"
  "$PY" "$DIR/send_morning_report.py"
} >> "$LOG" 2>&1
