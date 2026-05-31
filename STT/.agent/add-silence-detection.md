# STT WebSocket API — Server buffers, client flushes

## How it works

The server buffers all audio chunks per connection. Nothing happens until the client explicitly flushes.

```
→ {"type":"audio", "audio":"<chunk1>"}    # buffered
→ {"type":"audio", "audio":"<chunk2>"}    # buffered
→ {"type":"audio", "audio":"<chunk3>"}    # buffered
→ {"type":"flush"}                        # transcribe all → done
← {"type":"text", "text":"...", "start":0, "end":1.2}
← {"type":"done", "segments":1}
```

## Messages

| Direction | Type | Fields | Description |
|-----------|------|--------|-------------|
| Client → | `configure` | `lang?` | Set language |
| Client → | `audio` | `audio: base64_wav` | Append 16kHz mono WAV chunk |
| Client → | `flush` | — | Transcribe buffer, return `done` |
| Client → | `stop` | — | Same as `flush` |
| Server ← | `configured` | `lang` | Language confirmed |
| Server ← | `text` | `text, start, end` | One transcribed segment |
| Server ← | `done` | `segments` | All segments sent |

## Frontend flow

1. Start mic capture, encode as 16kHz mono 16-bit WAV
2. Chunk at whatever interval (100-500ms fine)
3. Stream with `{"type":"audio", "audio":"<base64>"}`
4. When user stops speaking (e.g. button release, silence VAD), send `{"type":"flush"}`
5. Receive transcribed `text` segments then `done`
6. Repeat for next utterance
