# STT — Speech-to-Text Daemon

Unix socket speech-to-text daemon using `faster-whisper`.
Keeps the model loaded between requests. Audio is received as raw
[PCM16](https://en.wikipedia.org/wiki/Pulse-code_modulation) signed
16-bit little-endian samples at 16 kHz.

**Model**: [openai/whisper-base](https://github.com/openai/whisper) via `faster-whisper` (~150 MB, auto-downloaded)

## Prerequisites

| Requirement | Minimum |
|---|---|
| Driver | NVIDIA driver 595+ (CUDA 13.2) |
| Python | 3.10+ |
| PyTorch | 2.6+ with CUDA |

> Tested on: RTX 2070 SUPER (8 GB), driver 595.71.05, CUDA 13.2

### Install

```bash
# torch-env should already exist — if not:
python3 -m venv ~/torch-env
~/torch-env/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
~/torch-env/bin/pip install faster-whisper scipy numpy
```

## Start

```bash
cd ~/Documents/code/ML/STT && ~/torch-env/bin/python stt_daemon.py
```

Or via the model manager:

```bash
~/Documents/code/ML/models.sh stt start
```

Listens on Unix socket `/tmp/stt-daemon.sock`.

## Protocol

Each connection is one turn of speech. The client connects, sends
raw PCM16 bytes, signals the end of the turn with
[`SHUT_WR`](https://man7.org/linux/man-pages/man2/shutdown.2.html),
waits for the transcription result as a single JSON line, then closes.

### Connection lifecycle

```
  Client                          Daemon
    │                                │
    │── connect ────────────────────→│ [accept(2)](https://man7.org/linux/man-pages/man2/accept.2.html)
    │                                │
    │── "en\n" ─────────────────────→│ optional language tag (skipped if empty)
    │                                │
    │── [raw PCM16 bytes] ──────────→│ buf += [recv(2)](https://man7.org/linux/man-pages/man2/recv.2.html)
    │── [raw PCM16 bytes] ──────────→│ buf += recv()
    │── [raw PCM16 bytes] ──────────→│ buf += recv()
    │                                │
    │── SHUT_WR ────────────────────→│ recv() → b""  ← EOF
    │                                │ transcribe(buf)
    │                                │
    │←── {"text":"...","segments"}   │ sendall(response)
    │                                │ close()
    │── recv() → response ──────────→│
    │                                │
    │── close() ────────────────────→│
```

### PCM16 format

Audio data is raw signed 16-bit **little-endian** samples at **16 kHz**.
No WAV header, no RIFF wrapper — just consecutive sample bytes.

A 1-second chunk at 16 kHz = 32 000 bytes (16 000 samples × 2 bytes each).

[PCM — Wikipedia](https://en.wikipedia.org/wiki/Pulse-code_modulation)

### SHUT_WR — half-close

[`shutdown(SHUT_WR)`](https://man7.org/linux/man-pages/man2/shutdown.2.html)
closes only the client's write side of the connection. The
client can still read — the daemon sends the response on the same socket.

The daemon sees this as [`recv()`](https://man7.org/linux/man-pages/man2/recv.2.html)
returning an empty byte string (`b""`), which signals
**"end of turn — transcribe now."**

No delimiter framing, no Base64, no special flush message. The byte stream
and the half-close are the framing.

## Client script

```bash
python stt_client.py /tmp/stt-daemon.sock input.wav [lang]
```

Converts WAV/PCM to int16 PCM, sends raw bytes, sends SHUT_WR, prints result.

## Events

Live events broadcast on the daemon's event socket
(`/tmp/monitor/STT-<pid>.sock`):

| Event | Fields |
|---|---|
| `stt.connection_open` | — |
| `stt.audio_chunk` | `samples`, `total_samples` |
| `stt.transcribe_done` | `text`, `duration`, `time_s`, `segments` |
| `stt.buffer_reject` | `total_samples`, `max_samples` |
| `stt.connection_close` | — |

Monitor with: `models daemon monitor`

## Configuration (`config.json`)

| Key | Default | Description |
|---|---|---|
| `model_size` | `base` | Whisper model size |
| `device` | `cuda` | Compute device |
| `compute_type` | `float16` | Model precision |
| `beam_size` | `5` | Beam search width |
| `max_connections` | `4` | Simultaneous client limit |
| `max_buffer_seconds` | `300` | Max audio buffer per client (5 min) |
| `verbose` | `false` | Extra logging |

## Files

```
STT/
├── stt_daemon.py     # Unix socket server, PCM16 loop
├── stt_client.py     # Streaming client
├── model.py          # load_engine() → STTEngine
├── config.json       # Model + daemon settings
├── config.py         # Config loader
├── README.md
└── .gitignore
```
