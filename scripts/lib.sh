VENV="$HOME/torch-env"

LLM_SOCKET="/tmp/llm-daemon.sock"
LLM_PID_FILE="/tmp/llm-daemon.pid"
TTS_SOCKET="/tmp/tts-daemon.sock"
TTS_PID_FILE="/tmp/tts-daemon.pid"
STT_SOCKET="/tmp/stt-daemon.sock"
STT_PID_FILE="/tmp/stt-daemon.pid"
GEN_SOCKET="/tmp/sdxl-daemon.sock"
GEN_PID_FILE="/tmp/sdxl-daemon.pid"

wait_for_socket() {
  local sock=$1 pid=$2 label=$3 log=$4 i
  for i in $(seq 1 120); do
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
  kill "$pid" 2>/dev/null && echo "  stopped $name (PID $pid)" || echo "  $name already stopped"
  rm -f "$pid_file"
}

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
