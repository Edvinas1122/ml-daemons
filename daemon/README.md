# daemon_builder

Generic Unix socket daemon wrapper. Boilerplate for three things every daemon needs:

- **CLI args** (`--socket`, `--event-socket`)
- **Socket lifecycle** (bind, listen, accept, cleanup dead socket files)
- **EventBus** (start/stop automatically, pass to handler)

## Usage

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
    max_connections=5,          # Semaphore limit
)
```

## Parameters

| Param | Required | Description |
|---|---|---|
| `name` | yes | Printed in logs |
| `default_socket` | yes | Unix socket path |
| `default_event_socket` | no | EventBus socket (`None` to disable) |
| `setup` | yes | `() -> state` — runs once before accept loop |
| `handle_client` | yes | `(conn, state, bus) -> None` — per-connection thread |
| `teardown` | no | `(state) -> None` — runs on shutdown |
| `max_connections` | no | Default 5 |

## Flexibility

The handler owns the connection completely — can do NDJSON streaming, raw binary, or request-response. The builder does not constrain protocol encoding.

## Connection concurrency

A `threading.Semaphore(max_connections)` gates thread-per-connection. The handler's thread releases the semaphore automatically in its `finally` block.
