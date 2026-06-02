#!/bin/bash
# Test STT daemon: send WAV as raw PCM16 + SHUT_WR, print result.
SOCK="/tmp/stt-daemon.sock"
WAV="${1:-$HOME/Documents/code/ML/TTS/voices/default.wav}"

[ -S "$SOCK" ] || { echo "STT daemon not running"; exit 1; }
[ -f "$WAV" ] || { echo "File not found: $WAV"; exit 1; }

# Convert WAV → raw PCM16, pipe with language line directly to socket
{
  echo "en"
  ffmpeg -y -i "$WAV" -f s16le -ar 16000 -ac 1 - 2>/dev/null
} | "$HOME/torch-env/bin/python3" -c "
import json, socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect('$SOCK')
s.sendall(sys.stdin.buffer.read())
s.shutdown(socket.SHUT_WR)
s.settimeout(15)
resp = json.loads(s.recv(65536).decode())
s.close()
print('Text:', resp.get('text',''))
if 'segments' in resp:
    for seg in resp['segments']:
        print(f'  [{seg[\"start\"]:.1f}-{seg[\"end\"]:.1f}] {seg[\"text\"]}')
if 'error' in resp:
    print('ERROR:', resp['error'])
"
