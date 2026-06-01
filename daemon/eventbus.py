#!/usr/bin/env python3
"""Push-based event bus for model daemons.

Each daemon creates an EventBus on a second Unix socket path (e.g.
/tmp/tts-events.sock).  Observers connect and receive live NDJSON events.
"""

import json
import os
import socket
import threading
import time


class EventBus:
    """Broadcasts NDJSON events to all connected subscribers."""

    def __init__(self, socket_path):
        self.socket_path = socket_path
        self._server = None
        self._subscribers: list[tuple] = []   # (file_obj, addr)
        self._lock = threading.Lock()
        self._running = False

    def start(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(8)
        os.chmod(self.socket_path, 0o777)
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True, name="evt-accept").start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server.accept()
                f = conn.makefile("wb")
                with self._lock:
                    self._subscribers.append((f, addr))
            except Exception:
                break

    def emit(self, event, **kw):
        """Broadcast event to all subscribers. Removes dead ones."""
        payload = json.dumps({"event": event, "t": round(time.time(), 3), **kw})
        msg = (payload + "\n").encode()
        with self._lock:
            dead = []
            for f, addr in self._subscribers:
                try:
                    f.write(msg)
                    f.flush()
                except Exception:
                    dead.append((f, addr))
            for item in dead:
                self._subscribers.remove(item)
                try:
                    item[0].close()
                except Exception:
                    pass

    @property
    def subscriber_count(self):
        with self._lock:
            return len(self._subscribers)

    def stop(self):
        self._running = False
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass
        with self._lock:
            for f, _ in self._subscribers:
                try:
                    f.close()
                except Exception:
                    pass
            self._subscribers.clear()
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception:
                pass
