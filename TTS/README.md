# TTS — Text-to-Speech Daemon

Unix socket text-to-speech daemon using `faster-qwen3-tts`.
Keeps the model loaded between requests. Audio is streamed back as raw
[PCM16](https://en.wikipedia.org/wiki/Pulse-code_modulation) signed
16-bit little-endian samples at 24 kHz.

**Model**: [Qwen/Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) via `faster-qwen3-tts` (~1.5 GB, auto-downloaded)

## Prerequisites

| Requirement | Minimum |
|---|---|
| Driver | NVIDIA driver 595+ (CUDA 13.2) |
| Python | 3.10+ |
| PyTorch | 2.6+ with CUDA |
| Model | [Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) |

> Tested on: RTX 2070 SUPER (8 GB), driver 595.71.05, CUDA 13.2

### Install

```bash
# torch-env should already exist — if not:
python3 -m venv ~/torch-env
~/torch-env/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
~/torch-env/bin/pip install faster-qwen3-tts scipy numpy
```

## Start

```bash
cd ~/Documents/code/ML/TTS && ~/torch-env/bin/python tts_daemon.py
```

Or via the model manager:

```bash
~/Documents/code/ML/models.sh tts start
```

Listens on Unix socket `/tmp/tts-daemon.sock`.

## Protocol

Each connection is one request. The client connects, sends a JSON
command, signals end of command with
[`SHUT_WR`](https://man7.org/linux/man-pages/man2/shutdown.2.html),
then reads the response until EOF.

### Audio format

Audio is raw signed 16-bit **little-endian** samples at **24 kHz**, mono.
No WAV header, no RIFF wrapper, no Base64 — just consecutive sample bytes.

A 1-second chunk at 24 kHz = 48 000 bytes (24 000 samples × 2 bytes each).

[PCM — Wikipedia](https://en.wikipedia.org/wiki/Pulse-code_modulation)

### Commands

| Command | Fields | Description |
|---|---|---|
| `synthesize` | `text` (required), `voice?`, `lang?` | Generate speech → raw PCM16 |
| `voices` | — | List available voices → JSON |

### Connection lifecycle (synthesize)

```
  Client                          Daemon
    │                                │
    │── connect ────────────────────→│ [accept(2)](https://man7.org/linux/man-pages/man2/accept.2.html)
    │                                │
    │── {"type":"synthesize",        │
    │    "text":"hello world"}\n ───→│ [send(2)](https://man7.org/linux/man-pages/man2/send.2.html)
    │                                │
    │── SHUT_WR ────────────────────→│ [shutdown(2)](https://man7.org/linux/man-pages/man2/shutdown.2.html)
    │                                │ generate(text)
    │                                │
    │←── [raw PCM16 bytes] ──────────│ [send(2)](https://man7.org/linux/man-pages/man2/send.2.html) — chunk 1
    │←── [raw PCM16 bytes] ──────────│ send() — chunk 2
    │←── [raw PCM16 bytes] ──────────│ send() — chunk N
    │                                │
    │←── SHUT_WR ────────────────────│ EOF — audio complete
    │                                │
    │── recv() → EOF ───────────────→│ [recv(2)](https://man7.org/linux/man-pages/man2/recv.2.html)
    │── close() ────────────────────→│
```

On error (e.g. empty text), the daemon closes the connection without
sending any data — the client receives EOF immediately.

### Reading the response

**synthesize:** read all bytes until EOF, interpret as signed 16-bit LE
PCM16 at 24 kHz.

**voices:** read all bytes until EOF, parse as JSON.

### SHUT_WR — half-close

[`shutdown(SHUT_WR)`](https://man7.org/linux/man-pages/man2/shutdown.2.html)
closes only the client's write side of the connection. The
client can still read — the daemon sends the response on the same socket.

This is the mirror of the STT protocol: instead of PCM16 in → JSON out,
it's JSON in → PCM16 out. Same framing, reversed direction.

No delimiter framing, no Base64, no NDJSON. The byte stream
and the half-close are the framing.

## Client script

```bash
python tts_client.py /tmp/tts-daemon.sock "Hello world" [voice] [lang]
```

Saves a WAV file to `~/Music/tts/`.

## Events

Live events broadcast on the daemon's event socket
(`/tmp/monitor/TTS-<pid>.sock`):

| Event | Fields |
|---|---|---|
| `tts.connection_open` | — |
| `tts.synthesize_start` | `text`, `voice`, `lang` |
| `tts.synthesize_done` | `text`, `samples` |
| `tts.voices_listed` | `count` |
| `tts.synthesize_error` | `error` |

Monitor with: `models daemon monitor`

## Configuration (`config.json`)

| Key | Default | Description |
|---|---|---|
| `model_path` | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | HF model ID or local path |
| `ws_port` | 8766 | (legacy WebSocket port) |
| `verbose` | `false` | Extra logging |
| `device` | `null` | CUDA device (null = auto) |

## Files

```
TTS/
├── tts_daemon.py     # Unix socket server, raw PCM16 output
├── tts_client.py     # WAV-saving client
├── model.py          # load_engine(), Session
├── config.json       # Model + daemon settings
├── config.py         # Config loader
├── voices/           # Reference voice WAVs
├── service.sh        # models.sh entry
├── README.md
└── .gitignore
```
