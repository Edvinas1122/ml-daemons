#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

usage() {
  cat <<'EOF'
Usage: models daemon monitor [-i pattern]

Live event feed from all daemon event sockets.

  -i pattern   Ignore events matching pattern (can repeat)
EOF
}

case "${1:-help}" in
  monitor)
    shift
    exec "$VENV/bin/python3" "$ML_ROOT/daemon/monitor.py" "$@"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
