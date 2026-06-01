#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

usage() {
  cat <<'EOF'
Usage: models tts <command>

  start                   Start TTS daemon
  stop                    Stop TTS daemon
  synthesize <text>       Synthesize text to speech
EOF
}

case "${1:-help}" in
  start)
    daemon_start "TTS" "$ML_ROOT/TTS" "tts_daemon.py" "$(service_sock TTS)" "$(service_pid TTS)" "$(service_log TTS)"
    ;;
  stop)
    kill_pid "$(service_pid TTS)" "TTS" "$(service_sock TTS)"
    ;;
  synthesize)
    shift
    local sock=$(service_sock TTS)
    if [ ! -S "$sock" ]; then
      echo "TTS daemon not running — start with: models tts start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/TTS/tts_client.py" "$sock" "$*"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
