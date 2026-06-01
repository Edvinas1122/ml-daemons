#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

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
    daemon_start "SDXL" "$ML_ROOT/Generate" "sdxl_daemon.py" "$(service_sock SDXL)" "$(service_pid SDXL)" "$(service_log SDXL)"
    ;;
  stop)
    kill_pid "$(service_pid SDXL)" "SDXL" "$(service_sock SDXL)"
    ;;
  gen|generate)
    shift
    sock=$(service_sock SDXL)
    if [ ! -S "$sock" ]; then
      echo "Generate daemon not running — start with: models generate start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/Generate/sdxl_client.py" "$sock" "$*"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
