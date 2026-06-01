#!/usr/bin/env python3
"""Send audio file to STT daemon as raw PCM16. Prints transcription."""

import json
import socket
import sys

import numpy as np


def main():
    if len(sys.argv) < 3:
        print("Usage: stt_client.py <socket_path> <audio_file> [lang]")
        sys.exit(1)

    sock_path = sys.argv[1]
    audio_path = sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else None

    ext = audio_path.rsplit(".", 1)[-1].lower()

    # Load audio → float32
    if ext in ("pcm", "raw"):
        with open(audio_path, "rb") as f:
            arr = np.frombuffer(f.read(), dtype=np.int16).astype(np.float32) / 32768.0
    elif ext == "wav":
        import scipy.io.wavfile as wav
        rate, arr = wav.read(audio_path)
        if arr.dtype == np.int16:
            arr = arr.astype(np.float32) / 32768.0
        if len(arr.shape) > 1:
            arr = arr.mean(axis=1)
    else:
        print(f"Unsupported format: {ext}")
        sys.exit(1)

    # float32 → int16 PCM bytes
    pcm_bytes = (arr * 32768.0).astype(np.int16).tobytes()

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)

    # First line is always a \n-terminated language tag (or just \n for default)
    s.sendall((lang or "").encode() + b"\n")

    # Raw PCM16
    s.sendall(pcm_bytes)
    s.shutdown(socket.SHUT_WR)

    # Read response
    resp = json.loads(s.recv(65536).decode())
    s.close()

    if "error" in resp:
        print(f"Error: {resp['error']}")
        sys.exit(1)

    print(f"Text: {resp['text']}")
    print(f"Duration: {resp['duration']}s  Time: {resp['time_s']}s")
    for seg in resp.get("segments", []):
        print(f"  [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")


if __name__ == "__main__":
    main()
