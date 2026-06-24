#!/bin/bash
# Cron wrapper: poll ESO seeing.last with a Python 3.7+ interpreter.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${LS4_SEEING_POLL_LOG:-/home/observer/logs/seeing_poll.log}"
PY="${LS4_PYTHON:-}"
for candidate in \
  /home/ls4/code/observer_venv/bin/python3 \
  /home/ls4/ls4_venv/bin/python3 \
  /home/ls4/observer_venv/bin/python3; do
  if [ -z "$PY" ] && [ -x "$candidate" ]; then
    PY=$candidate
  fi
done
if [ -z "$PY" ]; then
  PY="$(command -v python3)"
fi
mkdir -p "$(dirname "$LOG")"
"$PY" "$DIR/poll_seeing_log.py" >> "$LOG" 2>&1
