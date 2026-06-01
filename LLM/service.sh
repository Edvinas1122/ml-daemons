#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/daemon/lib.sh"

usage() {
  cat <<'EOF'
Usage: models llm <command>

  start              Start LLM daemon
  stop               Stop LLM daemon
  <text>             Chat with LLM
EOF
}

case "${1:-help}" in
  start)
    daemon_start "LLM" "$ML_ROOT/LLM" "llm_daemon.py" "$LLM_SOCKET" "$LLM_PID_FILE" /tmp/llm-daemon.log
    ;;
  stop)
    kill_pid "$LLM_PID_FILE" "LLM" "$LLM_SOCKET"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    if [ ! -S "$LLM_SOCKET" ]; then
      echo "LLM daemon not running — start with: models llm start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/LLM/llm_client.py" "$LLM_SOCKET" "$*"
    ;;
esac
