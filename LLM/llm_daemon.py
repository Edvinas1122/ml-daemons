#!/usr/bin/env python3
"""LLM daemon — pure chat, no tool calling. Built with daemon_builder."""

import json
import os
import sys
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

    bus.emit("llm.connection_open")
    
    # Read request
    data = conn.recv(65536).decode()
    bus.emit("llm.read_done", bytes=len(data))

    msg = json.loads(data)
    bus.emit("llm.parse_done")

    # Validate request
    if msg.get("type") != "chat":
        conn.sendall(json.dumps({"type": "error", "error": "use type=chat"}).encode())
        bus.emit("llm.request_invalid", type=msg.get("type"))
        return

    messages = msg.get("messages", [])
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    tokens = tokenizer(prompt, return_tensors="pt").to(model.device)
    bus.emit("llm.tokenize_done", tokens=tokens['input_ids'].shape[1])

    max_tokens = msg.get("max_tokens", config.get("max_tokens", 10000))
    temperature = msg.get("temperature", config.get("temperature", 0.7))

    # Setup streaming
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    gen_kwargs = dict(
        **tokens,
        max_new_tokens=max_tokens,
        temperature=temperature,
        do_sample=temperature > 0,
        streamer=streamer,
    )

    bus.emit("llm.generate_start", messages=len(messages), max_tokens=max_tokens)

    # Start generation thread
    thread = Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
    thread.start()

    # Stream tokens
    out = conn.makefile("wb")
    full = []
    
    for token in streamer:
        full.append(token)
        line = json.dumps({"type": "token", "content": token}).encode() + b"\n"
        out.write(line)
        out.flush()

    # Send completion
    text = "".join(full)
    out.write(json.dumps({"type": "done", "content": text}).encode() + b"\n")
    out.flush()
    out.close()

    bus.emit("llm.generate_done", tokens=len(text.split()))


if __name__ == "__main__":
    run_daemon(
        "LLM",
        default_socket="/tmp/llm-daemon.sock",
        setup=setup,
        handle_client=handle_client,
        startup_timeout=120,
        connection_timeout=120
    )