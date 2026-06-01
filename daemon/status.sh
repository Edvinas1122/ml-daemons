#!/usr/bin/env bash
ML_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ML_ROOT/scripts/lib.sh"

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
echo "║  Services:"
check_unix_socket "$TTS_SOCKET"  "$TTS_PID_FILE"  "TTS"    || true
check_unix_socket "$STT_SOCKET"  "$STT_PID_FILE"  "STT"    || true
check_unix_socket "$GEN_SOCKET"  "$GEN_PID_FILE"  "Generate" || true
check_unix_socket "$LLM_SOCKET"  "$LLM_PID_FILE"  "LLM"    || true
echo "╚══════════════════════════════════════"
