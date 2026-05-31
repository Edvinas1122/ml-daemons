# Monitor — Model Daemon Manager

Unified CLI to start, stop, and monitor GPU AI model daemons (TTS, STT, SDXL) on a single machine.

## Quick start

```bash
./models.sh voice start      # TTS + STT daemons (stops SDXL first)
./models.sh image start      # SDXL daemon (stops TTS + STT first)
./models.sh status           # GPU VRAM + running daemons
./models.sh monitor          # Live event feed from all daemons
```

## Commands

| Command | Description |
|---|---|
| `voice start` | Start TTS and STT daemons (kills SDXL first) |
| `voice stop` | Stop both TTS and STT |
| `voice tts <text>` | Synthesize speech via TTS daemon |
| `voice stt <file.wav>` | Transcribe audio via STT daemon |
| `image start` | Start SDXL daemon (kills TTS + STT first) |
| `image stop` | Stop SDXL daemon |
| `image gen <prompt>` | Generate image via SDXL daemon |
| `status` | Show GPU VRAM and running daemons |
| `monitor [-i pattern]` | Live event feed (`-i stt.audio_chunk` to filter noise) |
| `tts start|stop` | Direct TTS control |
| `stt start|stop` | Direct STT control |
| `help` | Show usage |

## Monitor examples

```bash
./models.sh monitor                     # full event feed
./models.sh monitor -i stt.audio_chunk  # hide audio chunk noise
./models.sh monitor -i *.chunk          # hide all chunk events
./models.sh monitor -i audio -i buffer  # multiple filters
```

## Architecture

```
┌───────────────────────────────────────────┐
│              models.sh                     │
│                                           │
│  voice start  ───► TTS daemon  (port)     │
│              └──► STT daemon  (port)      │
│  image start ───► SDXL daemon (socket)    │
│                                           │
│  status ──► nvidia-smi + socket checks    │
│  monitor ──► event sockets                │
└───────────────────────────────────────────┘
```

Conflicts are managed automatically — starting image kills voice, starting voice kills image.

## Daemons

Each daemon keeps its model loaded in memory and communicates over Unix sockets:

| Daemon | Request socket | Event socket | Model |
|---|---|---|---|
| TTS | `/tmp/tts-daemon.sock` | `/tmp/tts-events.sock` | Qwen3-TTS-12Hz-0.6B |
| STT | `/tmp/stt-daemon.sock` | `/tmp/stt-events.sock` | faster-whisper base |
| SDXL | `/tmp/sdxl-daemon.sock` | `/tmp/sdxl-events.sock` | SDXL-base-1.0 |

## Event system

Each daemon broadcasts live NDJSON events on its event socket.
`models.sh monitor` subscribes to all three and merges them into a color-coded feed.

```
19:02:36 [STT] stt.connection_open
19:02:36 [STT] stt.audio_chunk        samples=16384  total_samples=16384
19:02:36 [STT] stt.transcribe_done    text=Close your eyes...  time_s=0.4
19:02:36 [STT] stt.connection_close
```

## Files

```
ML/monitor/
├── models.sh              # Main CLI
├── monitor.py             # Live event viewer
├── eventbus.py            # EventBus class (imported by daemons)
├── .agent/
│   └── eventbus-design.md # Full event system design doc
├── README.md              # This file
```

Daemon source lives in sibling directories:

```
ML/
├── TTS/tts_daemon.py
├── STT/stt_daemon.py
├── Generate/sdxl_daemon.py
└── monitor/
```

## GPU resource notes

- TTS + STT: ~7 GB VRAM (at 512 context)
- SDXL: idle ~0.4 GB (CPU offload), spikes during inference
- Switch between voice and image with `voice start` / `image start`
