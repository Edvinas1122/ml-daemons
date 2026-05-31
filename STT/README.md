# STT — Speech-to-Text Daemon

Unix socket speech-to-text daemon using `faster-whisper`.
Keeps the model loaded between requests. Streaming NDJSON protocol.

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

Newline-delimited JSON (NDJSON) over a single connection.

### Client → Daemon

```
{"type":"lang","lang":"en"}\n                                    (optional)
{"type":"audio","data":"<base64_pcm16>","format":"pcm16"}\n       (one or more chunks)
{"type":"flush"}\n                                                 (transcribe and close)
```

Chunk size: 32 KB PCM (≈1 second at 16 kHz). Send sequentially, flush after the last chunk.
Set language once with `lang` before the first `audio` message.

### Daemon → Client

```json
{"type":"done","text":"...","segments":[...],"duration":9.22,"time_s":0.34}
```

`segments` is an array of `{"text":"...","start":0.0,"end":6.5}`.

## Example

```bash
# Via models.sh
~/Documents/code/ML/models.sh voice stt input.wav

# Directly
echo '{"type":"lang","lang":"en"}
{"type":"audio","data":"<base64>","format":"pcm16"}
{"type":"flush"}' | nc -U /tmp/stt-daemon.sock
```

## Client script

```bash
python stt_client.py /tmp/stt-daemon.sock input.wav [lang]
```

Converts WAV/PCM to int16 PCM, streams in 32 KB chunks, prints transcription.

## Events

Live events broadcast on `/tmp/stt-events.sock`:

| Event | Fields |
|---|---|
| `stt.connection_open` | — |
| `stt.audio_chunk` | `samples`, `total_samples` |
| `stt.transcribe_done` | `text`, `duration`, `time_s`, `segments` |
| `stt.buffer_reject` | `total_samples`, `max_samples` |
| `stt.connection_close` | — |

Monitor with: `models.sh monitor`

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
├── src/
│   ├── stt_daemon.py     # Unix socket server, NDJSON loop
│   ├── stt_client.py     # Streaming client
│   ├── model.py          # load_engine() → STTEngine
│   └── __init__.py
├── config.json           # Model + daemon settings
├── config.py             # Config loader
├── .agent/               # Design docs, adapters
├── README.md
└── .gitignore
```

## Old WebSocket server

The previous WebSocket-based server (`server.py`, `handler.py`, `buffer.py`) has been
removed. The daemon uses Unix sockets for lower overhead and persistent model loading.
