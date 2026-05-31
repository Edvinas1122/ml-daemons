#!/usr/bin/env python3
"""Send audio file to STT daemon in streaming PCM chunks. Prints transcription."""

import base64
import io
import json
import socket
import sys

import numpy as np
import scipy.io.wavfile as wav


def main():
    if len(sys.argv) < 3:
        print("Usage: stt_client.py <socket_path> <audio_file> [lang]")
        sys.exit(1)

    sock_path = sys.argv[1]
    audio_path = sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else None

    ext = audio_path.rsplit(".", 1)[-1].lower()

    # Load audio and convert to PCM float32
    if ext in ("pcm", "raw"):
        with open(audio_path, "rb") as f:
            raw = f.read()
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        rate, arr = wav.read(audio_path)
        if arr.dtype == np.int16:
            arr = arr.astype(np.float32) / 32768.0
        if len(arr.shape) > 1:
            arr = arr.mean(axis=1)

    # Convert float32 back to int16 PCM bytes for streaming
    pcm_bytes = (arr * 32768.0).astype(np.int16).tobytes()

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    out = s.makefile("wb")
    inp = s.makefile("rb")

    if lang:
        out.write(json.dumps({"type": "lang", "lang": lang}).encode() + b"\n")
        out.flush()

    chunk_size = 32768  # 32 KB of PCM = ~1 second at 16 kHz
    offset = 0
    while offset < len(pcm_bytes):
        chunk = pcm_bytes[offset:offset + chunk_size]
        b64 = base64.b64encode(chunk).decode()
        out.write(json.dumps({"type": "audio", "data": b64, "format": "pcm16"}).encode() + b"\n")
        out.flush()
        offset += chunk_size

    flush_msg = {"type": "flush"}
    if lang:
        flush_msg["lang"] = lang
    out.write(json.dumps(flush_msg).encode() + b"\n")
    out.flush()
    out.close()

    line = inp.readline()
    inp.close()
    s.close()

    if not line:
        print("Error: no response from daemon")
        sys.exit(1)

    resp = json.loads(line.decode())
    if "error" in resp:
        print(f"Error: {resp['error']}")
        sys.exit(1)

    print(f"Text: {resp['text']}")
    print(f"Duration: {resp['duration']}s  Time: {resp['time_s']}s")
    for seg in resp.get("segments", []):
        print(f"  [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")


if __name__ == "__main__":
    main()
