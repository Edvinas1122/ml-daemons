#!/usr/bin/env python3
"""Send prompt to SDXL daemon and print result."""

import json
import socket
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: sdxl_client.py <socket_path> <prompt>")
        sys.exit(1)

    sock_path = sys.argv[1]
    prompt = sys.argv[2]

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(json.dumps({"prompt": prompt}).encode())
    s.shutdown(socket.SHUT_WR)
    resp = json.loads(s.recv(65536).decode())
    s.close()

    if "error" in resp:
        print(f"Error: {resp['error']}")
        sys.exit(1)
    else:
        print(f"Saved: {resp['path']}")


if __name__ == "__main__":
    main()
