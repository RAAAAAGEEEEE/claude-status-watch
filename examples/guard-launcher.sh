#!/bin/bash
# Example job launcher: pauses (exit 75) while the model of the job is affected by a Claude incident.
# Usage: guard-launcher.sh <model> <command...>   e.g. guard-launcher.sh claude-sonnet-5-5 ./nightly-job.sh
set -u
MODEL="$1"; shift
WATCH="${CSW_DIR:-$HOME/claude-status-watch}/claude_status_watch.py"
STATUS="${CSW_STATUS_FILE:-$HOME/.claude-status-watch/status.json}"
REASON=$(python3 -I "$WATCH" guard --status-file "$STATUS" --model "$MODEL"); RC=$?
if [ "$RC" -eq 75 ]; then
  echo "$(date -Is) $REASON" >> "$HOME/.claude-status-watch/pause.log"
  exit 75
fi
exec "$@"
