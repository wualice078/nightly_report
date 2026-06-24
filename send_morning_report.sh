#!/bin/bash
# Morning cron wrapper — logs output for debugging.
# Install on mountain (observer): 0 7 * * * /home/observer/nightly_report/send_morning_report.sh
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/reports/cron_morning.log"
PY="${LS4_PYTHON:-}"
for candidate in \
  /home/ls4/ls4_venv/bin/python3 \
  /home/ls4/code/observer_venv/bin/python3 \
  /home/ls4/observer_venv/bin/python3; do
  if [ -z "$PY" ] && [ -x "$candidate" ]; then
    PY=$candidate
  fi
done
if [ -z "$PY" ]; then
  PY="$(command -v python3)"
fi
export LS4_OBSERVER_ROOT="${LS4_OBSERVER_ROOT:-/home/observer}"
export LS4_ROOT="${LS4_ROOT:-/home/observer}"
export LS4_DATA_ROOT="${LS4_DATA_ROOT:-/home/observer/data:/home/ls4/data}"
export LS4_OBSPLAN_ROOT="${LS4_OBSPLAN_ROOT:-/home/observer/obsplans:/home/ls4/obsplans}"
export LS4_DOME_DAEMON_LOG="${LS4_DOME_DAEMON_LOG:-$LS4_ROOT/logs/dome_daemon.log}"
export LS4_QUESTCTL_LOG_DIR="${LS4_QUESTCTL_LOG_DIR:-$LS4_ROOT/logs}"
export LS4_DIMM_LOG="${LS4_DIMM_LOG:-$LS4_ROOT/logs/dimm.logs}"
export LS4_LIVE_ONLY="${LS4_LIVE_ONLY:-1}"
mkdir -p "$DIR/reports"
{
  echo "=== $(date -Iseconds) ==="
  echo "package=$DIR observer_root=$LS4_OBSERVER_ROOT python=$PY"
  "$PY" "$DIR/send_morning_report.py"
} >> "$LOG" 2>&1
