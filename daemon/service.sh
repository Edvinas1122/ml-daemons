#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

usage() {
  cat <<'EOF'
Usage: models daemon <command>

  status              GPU VRAM + running daemons
  monitor [-i pattern] Live event feed from all daemons
EOF
}

case "${1:-help}" in
  status)
    exec "$ML_ROOT/daemon/status.sh" "$@"
    ;;
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
