#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

usage() {
  cat <<'EOF'
Usage: models generate <command>

  start              Start image generation daemon
  stop               Stop image generation daemon
  gen <prompt>       Generate an image from a prompt
EOF
}

case "${1:-help}" in
  start)
    daemon_start "SDXL" "$ML_ROOT/Generate" "sdxl_daemon.py" "$GEN_SOCKET" "$GEN_PID_FILE" /tmp/sdxl-daemon.log
    ;;
  stop)
    kill_pid "$GEN_PID_FILE" "SDXL"
    rm -f "$GEN_SOCKET"
    ;;
  gen|generate)
    shift
    if [ ! -S "$GEN_SOCKET" ]; then
      echo "Generate daemon not running — start with: models generate start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/Generate/sdxl_client.py" "$GEN_SOCKET" "$*"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
