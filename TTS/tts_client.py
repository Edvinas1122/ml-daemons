#!/usr/bin/env python3
"""Send TTS request to daemon, read raw PCM16, save WAV."""

import json
import os
import socket
import sys
from datetime import datetime

import numpy as np
import scipy.io.wavfile as wav

import config


def main():
    if len(sys.argv) < 3:
        print("Usage: tts_client.py <socket_path> <text> [voice] [lang]")
        sys.exit(1)

    sock_path = sys.argv[1]
    text = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else None
    lang = sys.argv[4] if len(sys.argv) > 4 else None

    msg = {"type": "synthesize", "text": text}
    if voice:
        msg["voice"] = voice
    if lang:
        msg["lang"] = lang

    # ── Send command + SHUT_WR ───────────────────────────────
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(json.dumps(msg).encode() + b"\n")
    s.shutdown(socket.SHUT_WR)

    # ── Read status line ─────────────────────────────────────
    f = s.makefile("rb")
    status_line = f.readline()
    status = json.loads(status_line.decode())

    if status.get("status") == "error":
        print(f"Error: {status['error']}", file=sys.stderr)
        sys.exit(1)

    sample_rate = status.get("sample_rate", 24000)
    print(f"Sample rate: {sample_rate}", file=sys.stderr)

    # ── Read raw PCM16 until EOF ─────────────────────────────
    pcm = f.read()
    f.close()
    s.close()

    if not pcm:
        print("Error: no audio received", file=sys.stderr)
        sys.exit(1)

    audio = np.frombuffer(pcm, dtype=np.int16)

    # ── Save WAV ─────────────────────────────────────────────
    out_dir = os.environ.get("TTS_OUTPUT_DIR",
                             os.path.expanduser(config.get("output_dir", "~/Music/tts")))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in text)[:60]
    fname = f"{ts}_{safe}.wav"
    path = os.path.join(out_dir, fname)
    os.makedirs(out_dir, exist_ok=True)
    wav.write(path, sample_rate, audio)

    print(f"Saved: {path}")
    print(f"Samples: {len(audio)} ({len(audio) / sample_rate:.1f}s)")


if __name__ == "__main__":
    main()
