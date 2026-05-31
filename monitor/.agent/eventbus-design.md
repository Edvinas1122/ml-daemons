# EventBus — Live Observability for Model Daemons

Each daemon opens a second Unix socket for push-based event streaming.
Observers connect and receive live NDJSON events without polling.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                      Daemon Process                   │
│                                                        │
│  ┌──────────────┐     ┌──────────────┐                │
│  │   Handler    │────►│              │                │
│  │  (thread)    │     │   EventBus   │                │
│  │              │  .emit()           │                │
│  │  synthesize  │     │              │                │
│  │  transcribe  │     │  subscribers │                │
│  │  generate    │     │  [f1, f2..]  │                │
│  └──────────────┘     └──────┬───────┘                │
│                              │                         │
│                              │ accept loop (daemon     │
│                              │ thread)                 │
└──────────────────────────────┼─────────────────────────┘
                               │
                    /tmp/<name>-events.sock
                               │
                    ┌──────────┼──────────┐
                    │          │          │
                 monitor    logwriter  dashboard
```

## Event flow

```
Daemon                       EventBus                  Observer
  │                             │                         │
  │  handle_client(conn)        │                         │
  │──bus.emit("stt.connection_open")                      │
  │                             ├── write NDJSON ────────►│
  │                             │                         │
  │  for each audio chunk       │                         │
  │──bus.emit("stt.audio_chunk")                         │
  │                             ├── write NDJSON ────────►│
  │                             │                         │
  │  on flush                   │                         │
  │──bus.emit("stt.transcribe_done")                      │
  │                             ├── write NDJSON ────────►│
  │                             │                         │
  │──bus.emit("stt.connection_close")                     │
  │                             ├── write NDJSON ────────►│
  │                             │                         │
```

## Protocol

Each event is one NDJSON line:

```json
{"event":"stt.audio_chunk","t":1746054156.032,"samples":16384,"total_samples":221310}
{"event":"stt.transcribe_done","t":1746054156.352,"text":"Close your eyes...","duration":13.83,"time_s":0.4,"segments":2}
{"event":"tts.synthesize_start","t":1746054160.123,"text":"Hello world","voice":"default","lang":"en"}
{"event":"sdxl.generate_done","t":1746054170.456,"prompt":"a cat","path":"/home/.../cat.png","steps":25}
```

| Field | Type | Description |
|---|---|---|
| `event` | string | Dot-separated: `{daemon}.{action}` |
| `t` | float | Unix timestamp (seconds) |
| `...` | varies | Event-specific fields |

## Events per daemon

### STT (`stt-events.sock`)

| Event | Fields |
|---|---|
| `stt.connection_open` | — |
| `stt.audio_chunk` | `samples`, `total_samples` |
| `stt.transcribe_done` | `text`, `duration`, `time_s`, `segments` |
| `stt.buffer_reject` | `total_samples`, `max_samples` |
| `stt.connection_close` | — |

### TTS (`tts-events.sock`)

| Event | Fields |
|---|---|
| `tts.connection_open` | `cmd` |
| `tts.synthesize_start` | `text`, `voice`, `lang` |
| `tts.synthesize_done` | `text`, `samples` |
| `tts.connection_close` | — |

### SDXL (`sdxl-events.sock`)

| Event | Fields |
|---|---|
| `sdxl.connection_open` | — |
| `sdxl.generate_start` | `prompt`, `steps` |
| `sdxl.generate_done` | `prompt`, `path`, `steps` |
| `sdxl.connection_close` | — |

## EventBus class

```python
class EventBus:
    def __init__(self, socket_path): ...
    def start(self):                  # creates socket, starts accept thread
    def emit(self, event, **kw):      # broadcasts NDJSON to all subscribers
    def stop(self):                   # closes socket, cleans up
```

- Accept thread runs in background, adds each connecting client as a subscriber
- `emit()` writes to all subscribers; dead ones are removed silently
- Thread-safe via `threading.Lock`

## Monitor

`models.sh monitor` connects to all three event sockets, merges streams, prints a
live color-coded feed:

```
19:02:36 [STT] stt.connection_open
19:02:36 [STT] stt.audio_chunk        samples=16384  total_samples=16384
19:02:36 [STT] stt.audio_chunk        samples=16384  total_samples=32768
...
19:02:36 [STT] stt.transcribe_done    text=Close your eyes...  time_s=0.4
19:02:36 [STT] stt.connection_close
```

Colors: TTS=green, STT=blue, SDXL=magenta.

## Files

| File | Role |
|---|---|
| `monitor/eventbus.py` | EventBus class (imported by all daemons) |
| `monitor/monitor.py` | Live event viewer |
| `monitor/models.sh` | `monitor` command entry point |
