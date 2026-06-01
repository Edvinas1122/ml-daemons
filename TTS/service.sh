#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

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
    daemon_start "TTS" "$ML_ROOT/TTS" "tts_daemon.py" "$TTS_SOCKET" "$TTS_PID_FILE" /tmp/tts-daemon.log
    ;;
  stop)
    kill_pid "$TTS_PID_FILE" "TTS" "$TTS_SOCKET"
    ;;
  synthesize)
    shift
    if [ ! -S "$TTS_SOCKET" ]; then
      echo "TTS daemon not running — start with: models tts start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/TTS/tts_client.py" "$TTS_SOCKET" "$*"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    usage
    ;;
esac
