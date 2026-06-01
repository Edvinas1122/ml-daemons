#!/usr/bin/env python3
import json
import os
import socket
import sys
import time

event_sock = sys.argv[1]
pid = int(sys.argv[2])
label = sys.argv[3]
timeout = int(sys.argv[4])

t0 = time.time()
deadline = t0 + timeout

while time.time() < deadline:
    remaining = deadline - time.time()
    if not os.path.exists(f"/proc/{pid}"):
        print(f"{label} failed", flush=True)
        sys.exit(1)
    if os.path.exists(event_sock):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(remaining)
            s.connect(event_sock)
            f = s.makefile("r")
            for line in f:
                ev = json.loads(line)
                if ev.get("status") == "ready":
                    print(f"{label} ready", flush=True)
                    sys.exit(0)
        except socket.timeout:
            print(f"{label} timed out", flush=True)
            sys.exit(1)
        except Exception:
            time.sleep(0.5)
    else:
        time.sleep(0.5)

print(f"{label} timed out", flush=True)
sys.exit(1)
