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
    daemon_start "LLM" "$ML_ROOT/LLM" "llm_daemon.py" "$(service_sock LLM)" "$(service_pid LLM)" "$(service_log LLM)"
    ;;
  stop)
    kill_pid "$(service_pid LLM)" "LLM" "$(service_sock LLM)"
    ;;
  help|--help|-h)
    usage
    ;;
  *)
    sock=$(service_sock LLM)
    if [ ! -S "$sock" ]; then
      echo "LLM daemon not running — start with: models llm start"
      exit 1
    fi
    "$VENV/bin/python3" "$ML_ROOT/LLM/llm_client.py" "$sock" "$*"
    ;;
esac
