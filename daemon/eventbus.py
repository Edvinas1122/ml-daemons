#!/usr/bin/env python3
"""Hybrid event bus + control socket for model daemons.

Single Unix socket. Protocol (one JSON line per connection):

  **Subscriber** (monitor, long-lived)
    Connect, send nothing, stay alive — receive pushed event NDJSON.

  **Event** (internal bus.emit calls)
    Client sends ``{"event": "name", ...}`` → broadcast to subscribers, close.

  **Command** (models daemon status, request-response)
    Client sends ``{"cmd": "name", ...}`` → execute handler, reply, close.
"""

import json
import os
import signal
import socket
import threading
import time


class EventBus:
    """Single Unix socket for broadcasting events and handling commands."""

    def __init__(self, socket_path):
        self.socket_path = socket_path
        self._server = None
        self._subscribers: list = []
        self._lock = threading.Lock()
        self._running = False
        self._handlers = {}
        self._ctrl_start = 0.0

    def set_handlers(self, handlers, state, bus, teardown_fn=None):
        """Register command handlers accessible over the socket.

        ``handlers`` is a dict ``{name: callable(cmd, state, bus) → dict}``.
        Built-in commands (ping, status, shutdown) are always available.
        """
        builtins = {}
        self._ctrl_state = state
        self._ctrl_bus = bus
        self._ctrl_start = time.time()

        def _ping(cmd, s, b):
            return {"ok": True}

        def _status(cmd, s, b):
            keys = list(s.keys()) if isinstance(s, dict) else None
            return {"pid": os.getpid(), "uptime": round(time.time() - self._ctrl_start, 2), "state_keys": keys}

        def _shutdown(cmd, s, b):
            os.kill(os.getpid(), signal.SIGTERM)
            return {"ok": True}

        builtins["ping"] = _ping
        builtins["status"] = _status
        builtins["shutdown"] = _shutdown

        self._handlers = dict(builtins)
        if handlers:
            self._handlers.update(handlers)

    def _handle_command(self, cmd, conn):
        name = cmd.get("cmd", "")
        fn = self._handlers.get(name)
        if fn:
            try:
                state = getattr(self, "_ctrl_state", None)
                bus = getattr(self, "_ctrl_bus", None)
                reply = fn(cmd, state, bus)
            except Exception as exc:
                reply = {"error": str(exc)}
        else:
            reply = {"error": f"unknown command: {name}"}
        payload = (json.dumps(reply) + "\n").encode()
        try:
            conn.sendall(payload)
        except Exception:
            pass

    def start(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(16)
        os.chmod(self.socket_path, 0o777)
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True, name="evt-ctrl").start()

    def _accept_loop(self):
        while self._running:
            try:
                conn, addr = self._server.accept()
            except Exception:
                break
            threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True, name="evt-conn").start()

    def _handle_conn(self, conn, addr):
        try:
            raw = conn.recv(65536)
        except Exception:
            raw = b""

        if not raw:
            # subscriber — keep alive and push events
            f = conn.makefile("wb")
            with self._lock:
                self._subscribers.append((f, addr))
            return

        data = raw.strip()
        try:
            msg = json.loads(data)
        except Exception:
            conn.close()
            return

        if "cmd" in msg:
            self._handle_command(msg, conn)
            conn.close()
        elif "event" in msg:
            # external event broadcast
            payload = data + b"\n"
            with self._lock:
                dead = []
                for f, _ in self._subscribers:
                    try:
                        f.write(payload)
                        f.flush()
                    except Exception:
                        dead.append(f)
                for f in dead:
                    self._subscribers.remove((f, None))
                    try:
                        f.close()
                    except Exception:
                        pass
            conn.close()
        else:
            conn.close()

    def emit(self, event, **kw):
        """Broadcast event to all subscribers. Removes dead ones."""
        payload = json.dumps({"event": event, "t": round(time.time(), 3), **kw})
        msg = (payload + "\n").encode()
        with self._lock:
            dead = []
            for f, _ in self._subscribers:
                try:
                    f.write(msg)
                    f.flush()
                except Exception:
                    dead.append(f)
            for f in dead:
                self._subscribers.remove((f, None))
                try:
                    f.close()
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
