# Daemon system

Reusable Unix socket framework for GPU model daemons. Each model runs as a persistent
process, keeps weights in GPU memory, and communicates via Unix sockets.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    models.sh                             │
│  ─── thin bash dispatcher                                │
│  models llm start  ──► LLM/service.sh ──► llm_daemon.py │
│  models tts start  ──► TTS/service.sh ──► tts_daemon.py │
│  models stt start  ──► STT/service.sh ──► stt_daemon.py │
│  models gen start  ──► Generate/service.sh → sdxl.py    │
│  models daemon status  ──► daemon/status.sh             │
│  models daemon monitor ──► daemon/monitor.py            │
└──────────────────────┬──────────────────────────────────┘
                       │ starts / stops / queries
                       ▼
┌──────────────────────────────────────────────────┐
│           daemon_builder.run_daemon()             │
│  ─────────────────────────────                    │
│  argparse → bind socket → accept loop            │
│  EventBus start/stop, Semaphore gating           │
│  calls setup() once, handle_client() per-connect │
└──────────────────────────────────────────────────┘
                       │
                       ▼  each daemon defines:
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ TTS      │ │ STT      │ │ SDXL     │ │ LLM      │
│ streaming│ │ NDJSON   │ │ req-resp │ │ streaming│
│ audio    │ │ in/out   │ │ image    │ │ tokens   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## How it works

1. **`daemon_builder.py`** provides `run_daemon()` — the common boilerplate:
   - Parses `--socket` and `--event-socket` CLI args
   - Creates and binds the Unix socket
   - Starts an `EventBus` for live monitoring events
   - Calls the daemon's `setup()` once to load the model
   - Accepts connections in a loop, spawning a thread per client
   - Gates concurrency with a `threading.Semaphore`

2. **Each service** (LLM, TTS, STT, Generate) implements two functions:
   - `setup()` — loads the model, returns a `state` dict
   - `handle_client(conn, state, bus)` — processes one request

3. **`EventBus`** (`eventbus.py`) — push-based broadcasting:
   - Each daemon opens a second event socket (`/tmp/*-events.sock`)
   - Daemons call `bus.emit("event_name", key=val, ...)` to broadcast
   - `daemon/monitor.py` subscribes to all event sockets and merges them
   - Supports `-i pattern` to filter noisy events

## Event monitor

```bash
models daemon monitor                    # full feed
models daemon monitor -i audio_chunk     # hide noisy events
models daemon monitor -i *.chunk
```

Color-coded NDJSON output:

```
19:02:36 [STT]  stt.connection_open
19:02:36 [STT]  stt.audio_chunk        samples=16384  total_samples=16384
19:02:37 [STT]  stt.transcribe_done    text=Close your eyes...  time_s=0.4
19:02:37 [STT]  stt.connection_close
```

## Socket map

| Daemon | Request socket | Event socket |
|---|---|---|
| LLM | `/tmp/llm-daemon.sock` | `/tmp/llm-events.sock` |
| TTS | `/tmp/tts-daemon.sock` | `/tmp/tts-events.sock` |
| STT | `/tmp/stt-daemon.sock` | `/tmp/stt-events.sock` |
| SDXL | `/tmp/sdxl-daemon.sock` | `/tmp/sdxl-events.sock` |

## daemon_builder reference

```python
from daemon_builder import run_daemon

def setup():
    return {"engine": load_engine(...)}

def handle_client(conn, state, bus):
    data = conn.recv(4096)
    result = state["engine"].process(data)
    conn.sendall(result)

run_daemon(
    "MyDaemon",
    default_socket="/tmp/myd.sock",
    default_event_socket="/tmp/myd-events.sock",
    setup=setup,
    handle_client=handle_client,
    max_connections=5,
)
```

### Parameters

| Param | Required | Description |
|---|---|---|
| `name` | yes | Printed in logs |
| `default_socket` | yes | Unix socket path |
| `default_event_socket` | no | EventBus socket (`None` to disable) |
| `setup` | yes | `() -> state` — runs once before accept loop |
| `handle_client` | yes | `(conn, state, bus)` — per-connection thread |
| `teardown` | no | `(state)` — runs on shutdown |
| `max_connections` | no | Default 5 |

The handler owns the connection completely — NDJSON streaming, raw binary, or
request-response. The builder does not constrain protocol encoding.

## Directory structure

```
ML/
├── models.sh                # Thin dispatcher
├── daemon/
│   ├── daemon_builder.py    # run_daemon() — socket server skeleton
│   ├── eventbus.py          # Push-based event broadcasting
│   ├── monitor.py           # Live event viewer (connects to all event sockets)
│   ├── status.sh            # GPU + running daemons status
│   └── service.sh           # Entry point for `models daemon status|monitor`
├── LLM/service.sh           # models llm start|stop|<text>
├── TTS/service.sh           # models tts start|stop|synthesize
├── STT/service.sh           # models stt start|stop|transcribe
└── Generate/service.sh      # models generate start|stop|gen
```
