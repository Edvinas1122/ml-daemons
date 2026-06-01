#!/usr/bin/env python3
"""Live event monitor — connects to daemon event sockets and prints a merged feed."""

import argparse
import json
import os
import select
import socket
import sys
import time

SOCKETS = [
    ("LLM", "/tmp/llm-events.sock"),
    ("TTS", "/tmp/tts-events.sock"),
    ("STT", "/tmp/stt-events.sock"),
    ("SDXL", "/tmp/sdxl-events.sock"),
]

COLORS = {
    "LLM": "\033[33m",
    "TTS": "\033[32m",
    "STT": "\033[34m",
    "SDXL": "\033[35m",
    "RESET": "\033[0m",
    "DIM": "\033[2m",
    "BOLD": "\033[1m",
}


def matches_ignore(event_name, patterns):
    for p in patterns:
        if p.endswith("*") and event_name.startswith(p[:-1]):
            return True
        if event_name == p:
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore", "-i", action="append", default=[],
                        help="Event pattern to hide (repeatable, supports trailing wildcard)")
    args = parser.parse_args()

    conns = {}
    for name, path in SOCKETS:
        if os.path.exists(path):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(path)
                f = s.makefile("rb")
                conns[name] = f
                print(f"{COLORS['DIM']}connected to {name} on {path}{COLORS['RESET']}", file=sys.stderr)
            except Exception as e:
                print(f"{COLORS['DIM']}{name}: {e}{COLORS['RESET']}", file=sys.stderr)

    if not conns:
        print("No daemon event sockets found. Start daemons first.")
        sys.exit(1)

    ignored = args.ignore
    if ignored:
        print(f"{COLORS['DIM']}ignoring: {', '.join(ignored)}{COLORS['RESET']}", file=sys.stderr)

    print(f"\n{COLORS['BOLD']}Listening... (Ctrl+C to stop){COLORS['RESET']}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        while conns:
            readable, _, _ = select.select(list(conns.values()), [], [], 1.0)
            for f in readable:
                name = next(n for n, v in conns.items() if v == f)
                line = f.readline()
                if not line:
                    del conns[name]
                    print(f"{COLORS['DIM']}{name} disconnected{COLORS['RESET']}", file=sys.stderr)
                    continue
                try:
                    event = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                ev = event.get("event", "?")
                if matches_ignore(ev, ignored):
                    continue

                t_str = time.strftime("%H:%M:%S", time.localtime(event.get("t", 0)))
                details = "  ".join(f"{k}={v}" for k, v in event.items() if k not in ("event", "t"))
                color = COLORS.get(name, "")
                reset = COLORS["RESET"]
                print(f"{color}{t_str} [{name}] {ev}{reset}  {COLORS['DIM']}{details}{reset}")
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        for f in conns.values():
            f.close()


if __name__ == "__main__":
    main()
