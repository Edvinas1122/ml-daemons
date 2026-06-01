#!/usr/bin/env python3
"""Live event monitor — connects to daemon event sockets and prints a merged feed."""

import argparse
import json
import os
import select
import socket
import sys
import time

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
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


def load_bus_dir():
    cfg = {"bus_dir": "/tmp/monitor/"}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg["bus_dir"].rstrip("/")


def connect_socket(name, path, conns):
    if name in conns:
        return
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(path)
        f = s.makefile("rb")
        conns[name] = f
        print(f"{COLORS['DIM']}connected to {name} on {path}{COLORS['RESET']}", file=sys.stderr)
    except Exception as e:
        print(f"{COLORS['DIM']}{name}: {e}{COLORS['RESET']}", file=sys.stderr)


def scan_and_connect(bus_dir, conns, seen):
    if not os.path.isdir(bus_dir):
        return
    for entry in os.listdir(bus_dir):
        if not entry.endswith(".sock"):
            continue
        path = os.path.join(bus_dir, entry)
        if path in seen:
            continue
        seen.add(path)
        name = entry.rsplit("-", 1)[0] if "-" in entry else entry[:-5]
        connect_socket(name, path, conns)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore", "-i", action="append", default=[],
                        help="Event pattern to hide (repeatable, supports trailing wildcard)")
    args = parser.parse_args()

    bus_dir = load_bus_dir()
    conns = {}
    seen = set()
    ignored = args.ignore

    if ignored:
        print(f"{COLORS['DIM']}ignoring: {', '.join(ignored)}{COLORS['RESET']}", file=sys.stderr)

    print(f"{COLORS['BOLD']}Watching {bus_dir}/ for daemon sockets... (Ctrl+C to stop){COLORS['RESET']}", file=sys.stderr)
    print(file=sys.stderr)

    try:
        while True:
            scan_and_connect(bus_dir, conns, seen)
            if not conns:
                select.select([], [], [], 1.0)
                continue

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
