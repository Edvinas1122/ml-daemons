# LLM — Large Language Model daemon

Unix socket daemon for chat inference. Uses `transformers` + `bitsandbytes` 4-bit quantization.

## Requirements

- NVIDIA GPU with **≥ 8 GB VRAM** (for 8B models in 4-bit)
- `~/torch-env` virtualenv

## Quick start

```bash
# 1. Install huggingface CLI (standalone, not in torch-env)
curl -LsSf https://hf.co/cli/install.sh | bash

# 2. Login with your HuggingFace token
hf auth login

# 3. Download a model
hf download Qwen/Qwen2.5-7B-Instruct

# 4. Start the daemon
models llm start

# 5. Chat
models llm "What is the capital of France?"
```

## Llama models

`meta-llama/Meta-Llama-3.1-8B-Instruct` is a **gated model** — you must:

1. Create an account at [huggingface.co](https://huggingface.co)
2. Generate a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
3. Accept the license at the model page: `https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct`
4. Login: `hf auth login`

Then download and use as usual.

If you prefer a model that works without extra steps:
```bash
models config llm Qwen/Qwen2.5-7B-Instruct
```

## Commands

| Command | Description |
|---|---|
| `models llm start` | Start the LLM daemon (loads model into GPU) |
| `models llm stop` | Stop the daemon (frees VRAM) |
| `models llm <text>` | Send a chat message, prints streaming response |
| `models status` | Check if daemon is running |
| `models list` | List all cached models with sizes |

## Socket

| Socket | Path |
|---|---|
| Request | `/tmp/llm-daemon.sock` |
| Events | `/tmp/llm-events.sock` |

## Protocol

Send NDJSON with `type=chat`:

```json
{"type": "chat", "messages": [{"role": "user", "content": "Hello"}]}
```

Response streams token-by-token:

```json
{"type": "token", "content": "Hello"}
{"type": "token", "content": "!"}
{"type": "done", "content": "Hello!"}
```

## Config

Edit `LLM/config.json`:

| Key | Default | Description |
|---|---|---|
| `model` | `meta-llama/...` | HuggingFace model ID |
| `device` | `cuda` | Torch device |
| `dtype` | `float16` | Torch dtype |
| `load_in_4bit` | `true` | 4-bit quantization via bitsandbytes |
| `max_tokens` | `1024` | Max new tokens per request |
| `temperature` | `0.7` | Sampling temperature |
