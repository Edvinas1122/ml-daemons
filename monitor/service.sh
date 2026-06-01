#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

usage() {
  cat <<'EOF'
Usage: models monitor [-i pattern]

Live event feed from running daemons. Passes through to monitor.py.

  -i pattern   Ignore events matching pattern (can repeat)
EOF
}

exec "$VENV/bin/python3" "$ML_ROOT/monitor/monitor.py" "$@"
