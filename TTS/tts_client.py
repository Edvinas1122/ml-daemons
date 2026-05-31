#!/usr/bin/env python3
"""Send TTS request to daemon, accumulate streaming audio, save WAV."""

import base64
import io
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

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(json.dumps(msg).encode())
    s.shutdown(socket.SHUT_WR)

    inp = s.makefile("rb")
    chunks = []
    sample_rate = None

    for line in inp:
        res = json.loads(line.decode())
        if res["type"] == "audio":
            sample_rate = res.get("sample_rate", sample_rate)
            chunks.append(np.frombuffer(base64.b64decode(res["data"]), dtype=np.int16))
        elif res["type"] == "done":
            break
        elif res["type"] == "error":
            print(f"Error: {res['error']}", file=sys.stderr)
            sys.exit(1)

    inp.close()
    s.close()

    if not chunks:
        print("Error: no audio received", file=sys.stderr)
        sys.exit(1)

    audio = np.concatenate(chunks)
    sr = sample_rate or 24000

    out_dir = os.environ.get("TTS_OUTPUT_DIR", os.path.expanduser(config.get("output_dir", "~/Music/tts")))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in text)[:60]
    fname = f"{ts}_{safe}.wav"
    path = os.path.join(out_dir, fname)
    os.makedirs(out_dir, exist_ok=True)
    wav.write(path, sr, audio)

    print(f"Saved: {path}")
    print(f"Sample rate: {sr}")


if __name__ == "__main__":
    main()
