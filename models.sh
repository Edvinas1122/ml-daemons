#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"

case "${1:-help}" in
  llm)    shift; exec "$DIR/LLM/service.sh" "$@" ;;
  tts)    shift; exec "$DIR/TTS/service.sh" "$@" ;;
  stt)    shift; exec "$DIR/STT/service.sh" "$@" ;;
  generate|image) shift; exec "$DIR/Generate/service.sh" "$@" ;;
  monitor) shift; exec "$DIR/monitor/service.sh" "$@" ;;
  status)
    shift
    exec "$DIR/scripts/status.sh" "$@"
    ;;
  list)
    shift
    exec "$DIR/scripts/list.sh" "$@"
    ;;
  help|--help|-h|"")
    echo "Usage: models <service> [args...]"
    echo ""
    echo "Services:"
    for d in "$DIR"/*/service.sh; do
      name=$(basename "$(dirname "$d")")
      echo "  $name"
    done
    echo "  status"
    echo "  list"
    echo ""
    echo "Run 'models <service>' for per-service help."
    ;;
  *)
    echo "Unknown: $1"
    echo "Run 'models help' for usage."
    exit 1
    ;;
esac
