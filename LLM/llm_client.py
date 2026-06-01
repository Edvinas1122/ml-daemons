#!/usr/bin/env python3
"""Send a chat message to LLM daemon, print streaming response."""

import json
import socket
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: llm_client.py <socket_path> <message>")
        sys.exit(1)

    sock_path = sys.argv[1]
    text = " ".join(sys.argv[2:])

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(sock_path)
    except ConnectionRefusedError:
        print("Error: LLM daemon not running", file=sys.stderr)
        sys.exit(1)

    s.sendall(json.dumps({
        "type": "chat",
        "messages": [{"role": "user", "content": text}],
    }).encode())
    s.shutdown(socket.SHUT_WR)

    inp = s.makefile("rb")
    got_output = False
    for line in inp:
        if not line.strip():
            continue
        res = json.loads(line.decode())
        rtype = res.get("type")
        if rtype == "token":
            print(res["content"], end="", flush=True)
            got_output = True
        elif rtype == "done":
            print()
            got_output = True
        elif rtype == "error":
            print(f"\nError: {res.get('error', 'unknown')}", file=sys.stderr)
            sys.exit(1)
    if not got_output:
        print("Error: no response from daemon", file=sys.stderr)
        sys.exit(1)
    inp.close()
    s.close()


if __name__ == "__main__":
    main()
