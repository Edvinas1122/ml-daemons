import { type Transcriber, type TranscriberSession, type TranscriberSessionOptions } from "@cloudflare/voice";

export class RtxSTT implements Transcriber {
  private url: string;
  constructor(url?: string) {
    this.url = url ?? "wss://stt.ml.edvinasmomkus.com";
  }
  createSession(options?: TranscriberSessionOptions): TranscriberSession {
    return new RtxSTTSession(this.url, options);
  }
}

class RtxSTTSession implements TranscriberSession {
  private ws: WebSocket | null = null;
  private options?: TranscriberSessionOptions;
  private ready: Promise<void>;
  private resolveReady: (() => void) | null = null;
  private closed = false;
  private closeOnDone = false;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;

  private static readonly SILENCE_MS = 1500;

  constructor(url: string, options?: TranscriberSessionOptions) {
    this.options = options;
    this.ready = new Promise((resolve) => { this.resolveReady = resolve; });
    this._connect(url);
  }

  private _connect(url: string) {
    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.addEventListener("open", () => {
      this.ws!.send(JSON.stringify({
        type: "configure",
        lang: this.options?.language ?? "en",
      }));
      this.resolveReady!();
    });

    let buffer: string[] = [];

    this.ws.addEventListener("message", (event) => {
      if (typeof event.data !== "string") return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "text") {
          buffer.push(msg.text);
          if (this.options?.onInterim) {
            this.options.onInterim(buffer.join(" "));
          }
        } else if (msg.type === "partial" || msg.type === "done") {
          if (buffer.length > 0 && this.options?.onUtterance) {
            this.options.onUtterance(buffer.join(" "));
          }
          buffer = [];
          if (msg.type === "done" && this.closeOnDone) {
            this.ws!.close();
          }
        }
      } catch {}
    });
  }

  feed(chunk: ArrayBuffer): void {
    if (this.closed || !this.ws) return;
    if (this.flushTimer) clearTimeout(this.flushTimer);

    const b64 = arrayBufferToBase64(chunk);
    this.ready.then(() => {
      this.ws!.send(JSON.stringify({ type: "audio", audio: b64, format: "pcm16" }));
    });

    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      this.ready.then(() => {
        this.ws!.send(JSON.stringify({ type: "flush" }));
      });
    }, RtxSTTSession.SILENCE_MS);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    this.closeOnDone = true;
    this.ready.then(() => {
      this.ws!.send(JSON.stringify({ type: "flush" }));
    });
  }
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}
