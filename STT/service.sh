#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

usage() {
  cat <<'EOF'
Usage: models stt <command>

  start                    Start STT daemon
  stop                     Stop STT daemon
  transcribe <file> [lang] Transcribe audio file
EOF
}

case "${1:-help}" in
  start)
    daemon_start "STT" "$ML_ROOT/STT" "stt_daemon.py" "$(service_sock STT)" "$(service_pid STT)" "$(service_log STT)"
    ;;
  stop)
    kill_pid "$(service_pid STT)" "STT" "$(service_sock STT)"
    ;;
  transcribe)
    shift
    sock=$(service_sock STT)
    if [ ! -S "$sock" ]; then
      echo "STT daemon not running — start with: models stt start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/STT/stt_client.py" "$sock" "$@"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
