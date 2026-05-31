#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
TTS_DIR="$DIR/TTS"
STT_DIR="$DIR/STT"
GEN_DIR="$DIR/Generate"
VENV="$HOME/torch-env"

TTS_SOCKET="/tmp/tts-daemon.sock"
STT_SOCKET="/tmp/stt-daemon.sock"
SDXL_SOCKET="/tmp/sdxl-daemon.sock"

TTS_PID_FILE="/tmp/tts-daemon.pid"
STT_PID_FILE="/tmp/stt-daemon.pid"
SDXL_PID_FILE="/tmp/sdxl-daemon.pid"

usage() {
  cat <<'EOF'
Usage: models.sh <command>

  voice start        Start TTS + STT daemons  (stops SDXL first)
  voice stop         Stop TTS + STT daemons
  voice tts <text>   Synthesize text via TTS daemon
  voice stt <file>   Transcribe audio via STT daemon

  image start        Start SDXL daemon  (stops TTS + STT first)
  image stop         Stop SDXL daemon
  image gen <prompt> Generate image via SDXL daemon

  status             GPU + running models
  monitor [-i pattern] Live event feed (--ignore audio_chunk, *.chunk)
  tts  start|stop    Direct TTS daemon control
  stt  start|stop    Direct STT daemon control
  help               This help
EOF
}

# ── helpers ──────────────────────────────────────────────

check_unix_socket() {
  local sock=$1 pid_file=$2 name=$3
  if [ -S "$sock" ] && [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "║    $name  socket $sock  running PID $(cat "$pid_file")"
    return 0
  else
    echo "║    $name  stopped"
    return 1
  fi
}

wait_for_socket() {
  local sock=$1 pid=$2 label=$3 log=$4
  local i
  for i in $(seq 1 60); do
    if [ -S "$sock" ]; then
      echo "$label ready at $sock"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$label failed — check $log"
      tail -3 "$log" 2>/dev/null
      return 1
    fi
    sleep 1
  done
  echo "$label timed out — check $log"
  return 1
}

kill_pid() {
  local pid_file=$1 name=$2
  if [ ! -f "$pid_file" ]; then
    echo "  $name not running"
    return 0
  fi
  local pid
  pid=$(cat "$pid_file")
  local sock
  sock=$(grep -oP 'socket=["\x27]?[^"\x27\s]+' <<< "" || true)
  kill "$pid" 2>/dev/null && echo "  stopped $name (PID $pid)" || echo "  $name already stopped"
  rm -f "$pid_file"
}

daemon_start() {
  local name=$1 dir=$2 script=$3 sock=$4 pid_file=$5 log=$6
  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (PID $(cat "$pid_file"))"
    return 0
  fi
  rm -f "$pid_file" "$sock"
  cd "$dir"
  nohup "$VENV/bin/python3" "$script" --socket "$sock" > "$log" 2>&1 &
  local pid=$!
  echo "$pid" > "$pid_file"
  wait_for_socket "$sock" "$pid" "$name" "$log"
}

# ── daemon commands ─────────────────────────────────────

tts_start()  { daemon_start "TTS"  "$TTS_DIR" "tts_daemon.py"  "$TTS_SOCKET"  "$TTS_PID_FILE"  /tmp/tts-daemon.log; }
tts_stop()   { kill_pid "$TTS_PID_FILE" TTS; rm -f "$TTS_SOCKET"; }
stt_start()  { daemon_start "STT"  "$STT_DIR" "stt_daemon.py"  "$STT_SOCKET"  "$STT_PID_FILE"  /tmp/stt-daemon.log; }
stt_stop()   { kill_pid "$STT_PID_FILE" STT; rm -f "$STT_SOCKET"; }
sdxl_start() { daemon_start "SDXL" "$GEN_DIR" "sdxl_daemon.py"    "$SDXL_SOCKET" "$SDXL_PID_FILE" /tmp/sdxl-daemon.log; }
sdxl_stop()  { kill_pid "$SDXL_PID_FILE" SDXL; rm -f "$SDXL_SOCKET"; }

tts_synthesize() {
  if [ ! -S "$TTS_SOCKET" ]; then
    echo "TTS daemon not running — start with: models.sh voice start"
    return 1
  fi
  "$VENV/bin/python3" "$TTS_DIR/tts_client.py" "$TTS_SOCKET" "$@"
}

stt_transcribe() {
  if [ ! -S "$STT_SOCKET" ]; then
    echo "STT daemon not running — start with: models.sh voice start"
    return 1
  fi
  "$VENV/bin/python3" "$STT_DIR/stt_client.py" "$STT_SOCKET" "$@"
}

sdxl_generate() {
  if [ ! -S "$SDXL_SOCKET" ]; then
    echo "SDXL daemon not running — start with: models.sh image start"
    return 1
  fi
  "$VENV/bin/python3" "$GEN_DIR/sdxl_client.py" "$SDXL_SOCKET" "$*"
}

# ── high-level ──────────────────────────────────────────

voice_start() {
  echo "Stopping SDXL (if running)..."
  sdxl_stop 2>/dev/null || true
  sleep 1
  echo "Starting TTS daemon..."
  tts_start
  echo "Starting STT daemon..."
  stt_start
  echo "Voice ready"
}

voice_stop() {
  echo "Stopping TTS..."
  tts_stop
  echo "Stopping STT..."
  stt_stop
  echo "Voice stopped"
}

image_start() {
  echo "Stopping TTS + STT (if running)..."
  tts_stop 2>/dev/null || true
  stt_stop 2>/dev/null || true
  sleep 1
  sdxl_start
}

image_stop() {
  sdxl_stop
}

# ── status ──────────────────────────────────────────────

status() {
  echo "╔══════════════════════════════════════╗"
  echo "║  AI Server Status                    ║"
  echo "╠══════════════════════════════════════╝"

  if command -v nvidia-smi &>/dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null | while IFS=, read -r name total used gpu_util; do
      name=$(echo "$name" | xargs)
      total=$(echo "$total" | xargs)
      used=$(echo "$used" | xargs)
      pct=$(python3 -c "t=${total%MiB};u=${used%MiB};print(f'{u/t*100:.0f}')" 2>/dev/null)
      echo "║  GPU: $name"
      echo "║  VRAM: $used / $total ($pct%)"
    done
  else
    echo "║  nvidia-smi not found"
  fi

  echo "║"
  echo "║  Models:"
  check_unix_socket "$TTS_SOCKET"  "$TTS_PID_FILE"  "TTS  (voice)"  || true
  check_unix_socket "$STT_SOCKET"  "$STT_PID_FILE"  "STT  (voice)"  || true
  check_unix_socket "$SDXL_SOCKET" "$SDXL_PID_FILE" "SDXL (image)"  || true
  echo "╚══════════════════════════════════════"
}

# ── dispatch ────────────────────────────────────────────

case "${1:-help}" in
  status)  status ;;

  voice)   shift; case "${1:-status}" in
             start)  voice_start ;;
             stop)   voice_stop ;;
             tts)    shift; tts_synthesize "$@" ;;
             stt)    shift; stt_transcribe "$@" ;;
             *)      echo "Usage: models.sh voice start|stop|tts <text>|stt <file>" ;;
           esac ;;

  image)   shift; case "${1:-start}" in
             start)    image_start ;;
             stop)     image_stop ;;
             gen|generate) shift; sdxl_generate "$@" ;;
             *)        echo "Usage: models.sh image start|stop|gen <prompt>" ;;
           esac ;;

  tts)     shift; case "${1:-status}" in
             start) tts_start ;;
             stop)  tts_stop ;;
             *)     check_unix_socket "$TTS_SOCKET" "$TTS_PID_FILE" "TTS" || true ;;
           esac ;;

  stt)     shift; case "${1:-status}" in
             start) stt_start ;;
             stop)  stt_stop ;;
             *)     check_unix_socket "$STT_SOCKET" "$STT_PID_FILE" "STT" || true ;;
           esac ;;

  monitor) shift; "$VENV/bin/python3" "$DIR/monitor/monitor.py" "$@" ;;

  help|--help|-h) usage ;;
  *)         echo "Unknown: $1"; usage; exit 1 ;;
esac
