ML_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

eval "$(python3 <<PYEOF
import json, os
cfg = json.load(open('$ML_DIR/daemon/config.json'))
print('declare VENV="' + os.path.expandvars(cfg['venv']) + '"')
print('declare BUS_DIR="' + os.path.expandvars(cfg['bus_dir']).rstrip('/') + '"')
PYEOF
)"

service_sock()  { echo "/tmp/$(echo "$1" | tr '[:upper:]' '[:lower:]')-daemon.sock"; }
service_pid()   { echo "/tmp/$(echo "$1" | tr '[:upper:]' '[:lower:]')-daemon.pid"; }
service_log()   { echo "/tmp/$(echo "$1" | tr '[:upper:]' '[:lower:]')-daemon.log"; }

wait_for_socket() {
  local sock=$1 pid=$2 label=$3 log=$4 timeout=${5:-300}
  local event_sock="$BUS_DIR/$label-$pid.sock"
  "$VENV/bin/python3" "$ML_DIR/scripts/wait_ready.py" "$event_sock" "$pid" "$label" "$timeout" || {
    echo "$label failed or timed out — check $log"
    tail -3 "$log" 2>/dev/null
    return 1
  }
  return 0
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
  rm -f "$sock" $BUS_DIR/"$name"-*.sock
}

check_unix_socket() {
  local name=$1 sock=$2 pid
  for bus_sock in "$BUS_DIR"/"$name"-*.sock; do
    [ -S "$bus_sock" ] || continue
    pid="${bus_sock##*-}"; pid="${pid%.sock}"
    if [ -S "$sock" ] && kill -0 "$pid" 2>/dev/null; then
      echo "║    $name  socket $sock  running PID $pid"
      return 0
    fi
  done
  echo "║    $name  stopped"
  return 1
}

daemon_start() {
  local name=$1 dir=$2 script=$3 sock=$4 pid_file=$5 log=$6
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
  wait_for_socket "$sock" "$pid" "$name" "$log"
}
