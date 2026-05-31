# Streaming STT over Unix Socket

## Protocol

Newline-delimited JSON (NDJSON) over a single Unix socket connection.
Each message is one JSON line terminated by `\n`.

### Client → Daemon

```
{"type":"lang","lang":"en"}\n                                    (optional, set language)
{"type":"audio","data":"<base64>","format":"pcm16"}\n             (one or more chunks)
{"type":"flush"}\n                                                 (transcribe and close)
```

### Daemon → Client

```
{"type":"done","text":"...","segments":[...],"duration":9.22,"time_s":0.34}\n
{"type":"error","message":"..."}\n
```

## Connection lifecycle

```
Client                              Daemon
  │                                   │
  ├── connect ──────────────────────► │
  │                                   │
  ├── {"lang":"en"}\n ───────────────►│  (optional)
  │                                   │
  ├── {"type":"audio","data":"<PCM chunk>"}\n ──►   buffers PCM
  ├── {"type":"audio","data":"<PCM chunk>"}\n ──►   buffers PCM
  ├── {"type":"audio","data":"<PCM chunk>"}\n ──►   buffers PCM
  │                                   │
  ├── {"type":"flush"}\n ────────────►│  transcribe(audio)
  │                                   │
  │◄── {"type":"done","text":"..."}\n ─┤
  │                                   │
close                               close
```

## Implementation

### Daemon (`src/stt_daemon.py`)

```python
def handle_client(conn, engine, max_buffer_samples):
    f = conn.makefile("rb")
    out = conn.makefile("wb")
    buffer = []
    total_samples = 0

    for line in f:
        msg = json.loads(line.decode())
        cmd = msg.get("type")

        if cmd == "audio":
            arr = decode_audio(raw, fmt)
            if total_samples + len(arr) > max_buffer_samples:
                send error, break
            buffer.append(arr)
            total_samples += len(arr)

        elif cmd == "flush":
            audio = np.concatenate(buffer)
            segments = engine.model.transcribe(audio, ...)
            send done response
            break

    f.close()
    out.close()
    conn.close()
```

### Client (`src/stt_client.py`)

1. Loads audio file, converts to int16 PCM bytes once (handles WAV and raw)
2. Streams 32 KB PCM chunks as base64 NDJSON lines
3. Ends with `{"type":"flush"}`
4. Reads one NDJSON response line

### Concurrency

```python
conn_sem = threading.Semaphore(config.max_connections)

while True:
    conn, _ = server.accept()
    conn_sem.acquire()
    threading.Thread(target=handle_with_cleanup, args=(conn, engine), daemon=True).start()
```

`conn_sem` prevents exceeding `max_connections`. Each client runs in its own thread
with a private buffer — no shared state. The model's `transcribe()` is serialised by
CUDA implicitly.

## Configuration (`config.json`)

| Key | Default | Description |
|---|---|---|
| `model_size` | `"base"` | Whisper model size |
| `device` | `"cuda"` | Compute device |
| `compute_type` | `"float16"` | Model precision |
| `beam_size` | `5` | Beam search width |
| `max_connections` | `4` | Simultaneous client limit |
| `max_buffer_seconds` | `300` | Max audio buffer per connection (5 min) |

## Files

| File | Role |
|---|---|
| `src/stt_daemon.py` | Unix socket server, NDJSON loop, buffers, transcribes |
| `src/stt_client.py` | Converts audio → PCM → base64, streams via NDJSON |
| `config.json` | Model + daemon settings |
| `src/model.py` | `load_engine()` — returns `STTEngine` wrapping `WhisperModel` |
