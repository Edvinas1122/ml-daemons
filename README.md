# ML Daemons

Unix socket daemon framework for GPU-accelerated AI models on a single NVIDIA RTX 2070 SUPER (8 GB).

## Services

| Service | Command | Description | Docs |
|---|---|---|---|
| LLM | `models llm start` | Chat inference (8B, 4-bit) | [LLM/](LLM/README.md) |
| TTS | `models tts start` | Qwen3-TTS speech synthesis | [TTS/](TTS/README.md) |
| STT | `models stt start` | faster-whisper transcription | [STT/](STT/README.md) |
| Generate | `models generate start` | SDXL image generation | [Generate/](Generate/README.md) |
| Daemon | `models daemon status` | GPU status + event monitor | [daemon/](daemon/README.md) |

## Quick start

```bash
# List all services
models

# Start a service
models llm start
models tts start

# Chat with LLM
models llm "What is the meaning of life?"

# Synthesize speech
models tts synthesize "Hello world"

# Transcribe audio
models stt transcribe recording.wav

# Generate an image
models generate gen "a cat wearing a hat"

# Check GPU and running daemons
models daemon status

# Live event feed
models daemon monitor
```

## Architecture

See [daemon/README.md](daemon/README.md) for the full architecture, socket map,
protocol details, and `daemon_builder` reference.

In short: each model runs as a persistent process with weights in GPU memory.
They communicate over Unix sockets with NDJSON streaming. An EventBus system
broadcasts live events for monitoring.

## Cached models

```bash
models list
```

All models are cached in `~/.cache/huggingface/hub/`. Use the standalone
`hf` CLI to download or manage them:

```bash
hf download Qwen/Qwen2.5-7B-Instruct
```

## Requirements

- Python 3.10+
- PyTorch with CUDA
- `~/torch-env` virtualenv
- NVIDIA GPU with ≥ 8 GB VRAM
