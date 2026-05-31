# Frontend — Cloudflare Voice Adapters

Two TypeScript classes implementing `@cloudflare/voice` provider interfaces:

## RtxSTT (`Transcriber`)

**File**: `.agent/rtx-stt-adapter.ts`
**URL**: `wss://stt.ml.edvinasmomkus.com`

### Protocol

| Direction | Message |
|-----------|---------|
| Client → | `{"type":"configure", "lang":"en"}` |
| Client → | `{"type":"audio", "audio":"<base64_pcm16>", "format":"pcm16"}` — raw 16kHz 16-bit PCM |
| Client → | `{"type":"flush"}` — transcribe all buffered audio |
| Server ← | `{"type":"text", "text":"...", "start":0, "end":1.2}` — one segment |
| Server ← | `{"type":"partial", "segments":2}` — flushed but more may come |
| Server ← | `{"type":"done", "segments":2}` — final |

### Behavior

- Sends audio as raw PCM (`format: "pcm16"`) — no WAV wrapper needed
- 1.5s client-side silence timer sends `flush` automatically
- `onInterim` fires as text segments arrive from flush
- `onUtterance` fires on `partial`/`done` with all segments joined
- `close()` sends final `flush` then closes after 500ms delay

### Usage

```typescript
import { RtxSTT } from "./.agent/rtx-stt-adapter";

class MyAgent extends VoiceAgent {
  transcriber = new RtxSTT();
}
```

## RtxTTS (`TTSProvider`, `StreamingTTSProvider`)

**File**: `.agent/rtx-tts-adapter.ts`
**URL**: `wss://tts.ml.edvinasmomkus.com`

### Protocol (WebSocket)

| Direction | Message |
|-----------|---------|
| Client → | `{"type":"synthesize", "text":"Hello", "id":"req-1"}` |
| Server ← | `{"type":"started", "id":"req-1"}` |
| Server ← | `{"type":"audio", "data":"<base64_wav>", "seq":0}` — each chunk is a WAV file |
| Server ← | `{"type":"done", "chunks":12}` |

### Behavior

- Connects via WebSocket to `wss://tts.ml.edvinasmomkus.com`
- `synthesizeStream`: strips WAV headers from each chunk → yields raw PCM (24000 Hz 16-bit mono)
- `synthesize`: collects all PCM, wraps in a single WAV header → returns one valid WAV
- Handles abort signal for cancellation
- No configure needed — voice/lang set per `synthesize` message field if needed

### Usage

```typescript
import { RtxTTS } from "./.agent/rtx-tts-adapter";

class MyAgent extends VoiceAgent {
  tts = new RtxTTS();
}
```

## Deployment notes

- Both use `wss://` through the Cloudflare tunnel (port 443)
- TTS tunnel domain: `tts.ml.edvinasmomkus.com`
- STT tunnel domain: `stt.ml.edvinasmomkus.com`
- SSL/TLS must be set to **Full** in Cloudflare dashboard for `wss://` to work
