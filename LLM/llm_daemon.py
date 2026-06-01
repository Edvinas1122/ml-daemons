#!/usr/bin/env python3
"""LLM daemon — pure chat, no tool calling. Built with daemon_builder."""

import json
import os
import sys
import time
from threading import Thread

_DIR = os.path.dirname(os.path.abspath(__file__))
_ML = os.path.dirname(_DIR)
sys.path.insert(0, _DIR)
sys.path.insert(0, os.path.join(_ML, "daemon"))

from transformers import TextIteratorStreamer

import config
from daemon_builder import run_daemon
from model import load_engine


def setup():
    model, tokenizer = load_engine(
        model_id=config.get("model"),
        dtype=config.get("dtype", "float16"),
        load_in_4bit=config.get("load_in_4bit", True),
    )
    return {"model": model, "tokenizer": tokenizer}


def handle_client(conn, state, bus):
    model = state["model"]
    tokenizer = state["tokenizer"]

    if bus:
        bus.emit("llm.connection_open")
    print("[handle_client] started", flush=True)

    try:
        conn.settimeout(5)
        print("[handle_client] reading request", flush=True)
        f = conn.makefile("rb")
        data = f.read().decode()
        f.close()
        conn.settimeout(None)
        print(f"[handle_client] read {len(data)} bytes", flush=True)
        if bus:
            bus.emit("llm.read_done", bytes=len(data))

        msg = json.loads(data)
        print("[handle_client] JSON parsed", flush=True)
        if bus:
            bus.emit("llm.parse_done")

        if msg.get("type") != "chat":
            conn.sendall(json.dumps({"type": "error", "error": "use type=chat"}).encode())
            return

        messages = msg.get("messages", [])
        print(f"[handle_client] messages={len(messages)}", flush=True)
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        print(f"[handle_client] prompt len={len(prompt)}", flush=True)

        tokens = tokenizer(prompt, return_tensors="pt").to(model.device)
        print(f"[handle_client] tokenized {tokens['input_ids'].shape[1]} tokens", flush=True)
        if bus:
            bus.emit("llm.tokenize_done", tokens=tokens['input_ids'].shape[1])

        max_tokens = msg.get("max_tokens", config.get("max_tokens", 1024))
        temperature = msg.get("temperature", config.get("temperature", 0.7))

        print(f"[handle_client] creating streamer (max_tokens={max_tokens})", flush=True)
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
        gen_kwargs = dict(
            **tokens,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            streamer=streamer,
        )

        if bus:
            bus.emit("llm.generate_start", messages=len(messages), max_tokens=max_tokens)

        print("[handle_client] starting generation thread", flush=True)
        thread = Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
        thread.start()

        out = conn.makefile("wb")
        full = []
        print("[handle_client] streaming output", flush=True)
        for token in streamer:
            full.append(token)
            line = json.dumps({"type": "token", "content": token}).encode() + b"\n"
            out.write(line)
            out.flush()

        text = "".join(full)
        print(f"[handle_client] done, {len(text)} chars", flush=True)
        out.write(json.dumps({"type": "done", "content": text}).encode() + b"\n")
        out.flush()
        out.close()

        if bus:
            bus.emit("llm.generate_done", tokens=len(text.split()))

    except Exception as e:
        print(f"[handle_client] ERROR: {e}", flush=True)
        if bus:
            bus.emit("llm.client_error", error=str(e))
        try:
            conn.sendall(json.dumps({"type": "error", "error": str(e)}).encode())
        except Exception:
            pass
    finally:
        print(f"[handle_client] closing connection", flush=True)
        if bus:
            bus.emit("llm.connection_close")
        conn.close()


if __name__ == "__main__":
    run_daemon(
        "LLM",
        default_socket="/tmp/llm-daemon.sock",
        setup=setup,
        handle_client=handle_client,
        startup_timeout=120,
    )
