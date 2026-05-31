import { type TTSProvider, type StreamingTTSProvider } from "@cloudflare/voice";

const WAV_SAMPLE_RATE = 24000; // Qwen3-TTS output rate

export class RtxTTS implements TTSProvider, StreamingTTSProvider {
  private url: string;

  constructor(url?: string) {
    this.url = url ?? "wss://tts.ml.edvinasmomkus.com";
  }

  async synthesize(text: string, signal?: AbortSignal): Promise<ArrayBuffer | null> {
    const pcmChunks: ArrayBuffer[] = [];
    try {
      for await (const pcm of this.synthesizeStream(text, signal)) {
        pcmChunks.push(pcm);
      }
    } catch {
      return null;
    }
    if (pcmChunks.length === 0) return null;

    const totalSamples = pcmChunks.reduce((s, c) => s + c.byteLength / 2, 0);
    const fullPcm = concatenateArrayBuffers(pcmChunks);
    return wrapWavHeader(fullPcm, WAV_SAMPLE_RATE);
  }

  async *synthesizeStream(text: string, signal?: AbortSignal): AsyncGenerator<ArrayBuffer> {
    const reqId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 10);

    const ws = new WebSocket(this.url);
    ws.binaryType = "arraybuffer";

    await new Promise<void>((resolve, reject) => {
      ws.addEventListener("open", () => resolve());
      ws.addEventListener("error", () => reject(new Error("WebSocket connection failed")));
      if (signal) {
        signal.addEventListener("abort", () => {
          ws.close();
          reject(signal.reason);
        }, { once: true });
      }
    });

    ws.send(JSON.stringify({ type: "synthesize", text, id: reqId }));

    let done = false;
    let wsError: Error | null = null;
    let resolveNext: (() => void) | null = null;
    const queue: ArrayBuffer[] = [];

    ws.addEventListener("message", (event) => {
      if (typeof event.data !== "string") return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "audio") {
          const wav = base64ToArrayBuffer(msg.data);
          const pcm = stripWavHeader(wav);
          queue.push(pcm);
        } else if (msg.type === "done") {
          done = true;
        } else if (msg.type === "error") {
          wsError = new Error(msg.message);
        }
      } catch {}
      resolveNext?.();
    });

    ws.addEventListener("error", () => {
      wsError = new Error("WebSocket error");
      resolveNext?.();
    });

    ws.addEventListener("close", () => {
      if (!done) wsError = new Error("WebSocket closed unexpectedly");
      resolveNext?.();
    });

    try {
      while (!done) {
        if (queue.length > 0) {
          yield queue.shift()!;
        } else {
          if (wsError) throw wsError;
          await new Promise<void>((resolve) => { resolveNext = resolve; });
          resolveNext = null;
        }
      }
    } finally {
      ws.close();
    }
  }
}

function stripWavHeader(wav: ArrayBuffer): ArrayBuffer {
  const view = new DataView(wav);
  const dataSize = view.getUint32(40, true);
  return wav.slice(44, 44 + dataSize);
}

function wrapWavHeader(pcm: ArrayBuffer, sampleRate: number): ArrayBuffer {
  const numChannels = 1;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign = numChannels * bitsPerSample / 8;
  const dataSize = pcm.byteLength;
  const buf = new ArrayBuffer(44 + dataSize);
  const v = new DataView(buf);

  writeStr(v, 0, "RIFF");
  v.setUint32(4, 36 + dataSize, true);
  writeStr(v, 8, "WAVE");
  writeStr(v, 12, "fmt ");
  v.setUint32(16, 16, true);
  v.setUint16(20, 1, true);
  v.setUint16(22, numChannels, true);
  v.setUint32(24, sampleRate, true);
  v.setUint32(28, byteRate, true);
  v.setUint16(32, blockAlign, true);
  v.setUint16(34, bitsPerSample, true);
  writeStr(v, 36, "data");
  v.setUint32(40, dataSize, true);
  new Uint8Array(buf, 44).set(new Uint8Array(pcm));
  return buf;
}

function writeStr(v: DataView, off: number, s: string) {
  for (let i = 0; i < s.length; i++) v.setUint8(off + i, s.charCodeAt(i));
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function concatenateArrayBuffers(buffers: ArrayBuffer[]): ArrayBuffer {
  const total = buffers.reduce((s, b) => s + b.byteLength, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const buf of buffers) {
    result.set(new Uint8Array(buf), offset);
    offset += buf.byteLength;
  }
  return result.buffer;
}
