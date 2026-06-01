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

    try:
        f = conn.makefile("rb")
        data = f.read().decode()
        f.close()
        msg = json.loads(data)

        if msg.get("type") != "chat":
            conn.sendall(json.dumps({"type": "error", "error": "use type=chat"}).encode())
            return

        messages = msg.get("messages", [])
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        tokens = tokenizer(prompt, return_tensors="pt").to(model.device)
        max_tokens = msg.get("max_tokens", config.get("max_tokens", 1024))
        temperature = msg.get("temperature", config.get("temperature", 0.7))

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

        thread = Thread(target=model.generate, kwargs=gen_kwargs, daemon=True)
        thread.start()

        out = conn.makefile("wb")
        full = []
        for token in streamer:
            full.append(token)
            line = json.dumps({"type": "token", "content": token}).encode() + b"\n"
            out.write(line)
            out.flush()

        text = "".join(full)
        out.write(json.dumps({"type": "done", "content": text}).encode() + b"\n")
        out.flush()
        out.close()

        if bus:
            bus.emit("llm.generate_done", tokens=len(text.split()))

    except Exception as e:
        try:
            conn.sendall(json.dumps({"type": "error", "error": str(e)}).encode())
        except Exception:
            pass
    finally:
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
