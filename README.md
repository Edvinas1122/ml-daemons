# ML Daemons

Unix socket daemons for TTS, STT, and image generation on a single NVIDIA RTX 2070 SUPER (8 GB).

```
models.sh          # unified CLI
daemon/            # daemon_builder — reusable socket skeleton
monitor/           # EventBus + live event viewer
TTS/               # Qwen3-TTS speech synthesis
STT/               # faster-whisper transcription
Generate/          # SDXL image generation
```

## Quick start

```bash
./models.sh voice start          # TTS + STT (kills SDXL first)
./models.sh voice tts "hello"    # synthesize speech
./models.sh voice stt input.wav  # transcribe audio

./models.sh image start          # SDXL (kills TTS + STT first)
./models.sh image gen "cat"      # generate image

./models.sh status               # GPU VRAM + running daemons
./models.sh monitor              # live event feed from all daemons
```

## models.sh reference

| Command | Action |
|---|---|
| `voice start` | Start TTS + STT — stops SDXL first |
| `voice stop` | Stop TTS + STT |
| `voice tts <text>` | Send text to TTS daemon, save `~/Music/tts/` |
| `voice stt <file>` | Transcribe audio via STT daemon |
| `image start` | Start SDXL — stops TTS + STT first |
| `image stop` | Stop SDXL |
| `image gen <prompt>` | Generate image, save `~/Pictures/generate/` |
| `status` | nvidia-smi VRAM + daemon socket/PID status |
| `monitor [-i pattern]` | Live event feed |
| `tts start\|stop` | Direct TTS control (skips conflict check) |
| `stt start\|stop` | Direct STT control |

Monitor supports `-i` to filter out noisy events:
```bash
./models.sh monitor -i stt.audio_chunk -i *.chunk
```

## Daemons

All daemons run persistently, keep their model loaded, and listen on Unix sockets.

### TTS — `/tmp/tts-daemon.sock`

Send a JSON request, receive streaming NDJSON lines (base64 audio chunks + `done`).

```python
# request
{"type": "synthesize", "text": "hello", "voice": "luke", "lang": "en"}

# response (streaming, one JSON line per chunk)
{"type": "audio", "data": "<base64 pcm16>", "sample_rate": 24000}
{"type": "done", "samples": 48000}

# other commands: configure, voices
```

VRAM: ~3.5 GB idle.

### STT — `/tmp/stt-daemon.sock`

Stream PCM chunks as NDJSON, then send `flush` to transcribe.

```python
# send audio chunks
{"type": "audio", "data": "<base64 pcm16>", "format": "pcm16"}
# optionally set language
{"type": "lang", "lang": "en"}
# trigger transcription
{"type": "flush", "lang": "en"}

# response
{"type": "done", "text": "...", "segments": [...], "duration": 2.5, "time_s": 0.4}
```

Config limits: `max_connections` (default 4), `max_buffer_seconds` (default 300). Exceeding buffer returns an error.

VRAM: ~3.5 GB idle.

### SDXL — `/tmp/sdxl-daemon.sock`

Single request-response JSON.

```python
# request
{"prompt": "a cat", "negative": "blurry", "steps": 25}

# response
{"path": "/home/.../Pictures/generate/cat.png"}
```

Uses `enable_model_cpu_offload()` + VAE slicing/tiling to fit 8 GB. VRAM: ~0.4 GB idle (spikes during inference).

## GPU resource management

TTS + STT use ~7 GB combined. SDXL spikes above that during inference. Only one group runs at a time:

- `voice start` kills SDXL before loading TTS + STT
- `image start` kills TTS + STT before loading SDXL
- Direct `tts start` / `stt start` skip conflict checks (use with care)

## Architecture

```
┌──────────────┐
│  models.sh   │  bash CLI — daemon lifecycle, client dispatch
└──────┬───────┘
       │  starts / stops / queries
       ▼
┌──────────────────────────────────────────────────┐
│  daemon_builder.run_daemon()                     │
│  ─────────────────────────────                    │
│  argparse → bind socket → accept loop            │
│  EventBus start/stop, Semaphore gating           │
│  calls setup() once, handle_client() per-connect │
└──────────────────────────────────────────────────┘
       │
       ▼  each daemon defines:
┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│  TTS setup  │ │ STT setup   │ │ SDXL setup       │
│  + handler  │ │ + handler   │ │ + handler        │
│  (streaming)│ │ (NDJSON in) │ │ (req-response)   │
└─────────────┘ └─────────────┘ └──────────────────┘
```

Each daemon also opens a second Unix socket (`/tmp/{tts,stt,sdxl}-events.sock`) for live NDJSON events. `models.sh monitor` subscribes to all three.

```
19:02:36 [STT]  stt.connection_open
19:02:36 [STT]  stt.audio_chunk        samples=16384  total_samples=16384
19:02:37 [STT]  stt.transcribe_done    text=Close your eyes...  time_s=0.4
19:02:37 [STT]  stt.connection_close
```

## Output directories

| Model | Path | Config key |
|---|---|---|
| TTS | `~/Music/tts/` | `TTS/config.json` → `output_dir` |
| SDXL | `~/Pictures/generate/` | `Generate/config.json` → `output_dir` |

Override via `TTS_OUTPUT_DIR` environment variable (TTS only).

## Socket map

| Daemon | Request | Events |
|---|---|---|
| TTS | `/tmp/tts-daemon.sock` | `/tmp/tts-events.sock` |
| STT | `/tmp/stt-daemon.sock` | `/tmp/stt-events.sock` |
| SDXL | `/tmp/sdxl-daemon.sock` | `/tmp/sdxl-events.sock` |

## Requirements

- Python 3.10+
- PyTorch with CUDA
- `~/torch-env` virtualenv (configured in `models.sh`)
- NVIDIA GPU with at least 8 GB VRAM
