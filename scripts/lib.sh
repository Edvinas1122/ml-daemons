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
  local sock=$1 pid=$2 label=$3 log=$4 timeout=${5:-60} i
  for i in $(seq 1 "$timeout"); do
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
  local pid_file=$1 name=$2 sock=$3
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    kill "$pid" 2>/dev/null && echo "  stopped $name (PID $pid)"
    rm -f "$pid_file"
  elif [ -S "$sock" ]; then
    echo "  $name PID file missing — killing process on $sock"
    fuser -k "$sock" 2>/dev/null && echo "  stopped $name"
    rm -f "$sock"
  else
    echo "  $name not running"
    return 0
  fi
  rm -f "$sock"
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
  local name=$1 dir=$2 script=$3 sock=$4 pid_file=$5 log=$6 timeout=${7:-60}
  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name already running (PID $(cat "$pid_file"))"
    return 0
  fi
  # Kill any ghost process still holding the socket
  if [ -S "$sock" ]; then
    echo "  $name ghost detected on $sock — killing"
    fuser -k "$sock" 2>/dev/null
    sleep 1
    rm -f "$sock"
  fi
  # Kill any process running this daemon script (survived after socket cleanup)
  local existing
  existing=$(pgrep -f "python3.*$script" 2>/dev/null || true)
  if [ -n "$existing" ]; then
    echo "  killing existing $name process(es): $(echo $existing | tr '\n' ' ')"
    kill $existing 2>/dev/null
    sleep 2
  fi
  rm -f "$pid_file"
  cd "$dir"
  nohup "$VENV/bin/python3" "$script" --socket "$sock" > "$log" 2>&1 &
  local pid=$!
  echo "$pid" > "$pid_file"
  wait_for_socket "$sock" "$pid" "$name" "$log" "$timeout"
}
