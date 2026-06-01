# daemon — Reusable Unix socket server framework

Generic skeleton for GPU model daemons. Each service provides a model, and the daemon
builder wraps it with socket lifecycle, concurrency gating, and event broadcasting.

## Components

| File | Role |
|---|---|
| `daemon_builder.py` | `run_daemon()` — socket server skeleton |
| `eventbus.py` | Push-based event broadcasting to subscribers |
| `monitor.py` | Live event viewer — connects to any daemon's event socket |
| `status.sh` | Reports GPU VRAM and checks if daemon sockets are alive |

## daemon_builder

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

A `threading.Semaphore(max_connections)` gates thread-per-connection.
The handler thread releases the semaphore automatically in its `finally` block.

### Lifecycle

```
run_daemon() called
  ├── argparse (--socket, --event-socket)
  ├── EventBus start (if event socket given)
  ├── setup() → state
  ├── bind + listen on socket
  ├── accept loop (spawns thread per connection)
  │    └── handle_client(conn, state, bus)
  └── on exit:
       ├── bus.stop()
       ├── teardown(state)
       └── unlink socket
```

## EventBus

Push-based NDJSON broadcasting. Each daemon creates an EventBus on a second Unix
socket. Observers connect and receive live events.

```python
from eventbus import EventBus

bus = EventBus("/tmp/myd-events.sock")
bus.start()
bus.emit("my.event", key="value", duration=1.2)
bus.stop()
```

Events are JSON lines: `{"event": "my.event", "t": 12345.678, "key": "value", ...}`

## Monitor

Connects to any daemon's event socket and prints a live color-coded feed.

```bash
models daemon monitor                    # full feed
models daemon monitor -i audio_chunk     # hide noisy events
models daemon monitor -i *.chunk         # wildcard patterns
```

Under the hood it's `daemon/monitor.py`. It scans `/tmp/*-events.sock` and
subscribes to all it finds.

## Status

Quick health check — GPU VRAM and daemon socket/PID liveness.

```bash
models daemon status
```
