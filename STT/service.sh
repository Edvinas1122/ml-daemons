#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

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
    daemon_start "STT" "$ML_ROOT/STT" "stt_daemon.py" "$STT_SOCKET" "$STT_PID_FILE" /tmp/stt-daemon.log
    ;;
  stop)
    kill_pid "$STT_PID_FILE" "STT" "$STT_SOCKET"
    ;;
  transcribe)
    shift
    if [ ! -S "$STT_SOCKET" ]; then
      echo "STT daemon not running — start with: models stt start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/STT/stt_client.py" "$STT_SOCKET" "$@"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
