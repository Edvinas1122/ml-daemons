#!/usr/bin/env python3
"""Generic Unix socket daemon builder.

Each daemon defines setup() and handle_client(); this wraps the common
boilerplate: socket creation, accept loop, event bus, concurrency limits.

Usage:
    from daemon_builder import run_daemon

    def setup():
        return {"engine": load_engine(...)}

    def handle_client(conn, state, bus):
        data = conn.recv(4096)
        result = state["engine"].process(data)
        conn.sendall(result)

    run_daemon("MyDaemon", default_socket="/tmp/mydaemon.sock",
               setup=setup, handle_client=handle_client)
"""

import argparse
import json
import os
import socket
import sys
import threading
import time

from eventbus import EventBus

def daemon_config():
    """Load daemon builder config from ``daemon/config.json``.

    Returns a dict with keys like ``venv`` and ``bus_dir``.
    """
    cfg = {"venv": os.path.expandvars("$HOME/torch-env"), "bus_dir": "/tmp/monitor/"}
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def parse_args(name, default_socket, startup_timeout):
    parser = argparse.ArgumentParser(description=f"{name} daemon")
    parser.add_argument("--socket", default=default_socket,
                        help=f"Unix socket path (default: {default_socket})")
    parser.add_argument("--startup-timeout", type=int, default=startup_timeout,
                        help="Seconds allowed for setup()")
    return parser.parse_args()


def handle_start(setup_fn, bus, startup_timeout):
    """Run setup_fn with a hard timeout, emit bus events.

    Returns (state, elapsed_seconds).
    """
    bus.emit("setup", status="started")
    t0 = time.time()
    timer = threading.Timer(startup_timeout, lambda: os._exit(1))
    timer.start()
    try:
        state = setup_fn()
    finally:
        timer.cancel()
    elapsed = time.time() - t0
    bus.emit("setup", status="ended", elapsed=round(elapsed, 2))
    return state, elapsed


def run_daemon(
    name,
    *,
    default_socket,
    setup,
    handle_client,
    teardown=None,
    max_connections=5,
    startup_timeout=60,
    connection_timeout=0, # default infinite
):
    """Run a Unix socket daemon.

    The event/control bus (single socket in ``daemon_config()["bus_dir"]``)
    handles both event broadcasting (for monitor) and JSON command-response
    (ping/status/shutdown).

    Parameters
    ----------
    name : str
        Human-readable daemon name (printed in logs).
    default_socket : str
        Default Unix socket path for client requests.
    setup : callable[[], any]
        Called once before the accept loop. Return value is passed to
        handle_client and teardown as `state`.
    handle_client : callable[[socket, any, EventBus], None]
        Called in a new thread per connection.
        Signature: (conn, state, bus).
    teardown : callable[[any], None] or None
        Called once on shutdown with the state object.
    max_connections : int
        Max concurrent client threads (passed to listen() and Semaphore).
    startup_timeout : int
        Maximum seconds to wait for setup() before giving up.
    """
    args = parse_args(name, default_socket, startup_timeout)

    cfg = daemon_config()
    bus_dir = cfg["bus_dir"]
    os.makedirs(bus_dir, exist_ok=True)
    bus_socket = os.path.join(bus_dir, f"{name}-{os.getpid()}.sock")
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    if os.path.exists(bus_socket):
        os.unlink(bus_socket)

    # ── Event/control bus ──────────────────────────────
    bus = EventBus(bus_socket)
    bus.start()

    # Create socket early so bash sees it immediately
    sem = threading.Semaphore(max_connections)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(args.socket)
    os.chmod(args.socket, 0o777)

    # ── Setup (with timeout) ───────────────────────────
    state, _ = handle_start(setup, bus, args.startup_timeout)

    # Register built-in control handlers on the bus
    bus.set_handlers({}, state, bus, teardown_fn=teardown)

    # Signal readiness to bash
    server.listen(max_connections)
    bus.emit("status", status="ready")
    print(f"{name} daemon ready on {args.socket}", flush=True)
    print(f"  bus on {bus_socket}", flush=True)

    def _handle(conn):
        if connection_timeout > 0:
            conn.settimeout(connection_timeout)
        try:
            bus.emit(f"{name}.connection_open")
            handle_client(conn, state, bus)
        except socket.timeout:
            bus.emit(f"{name}.connection_timeout")
            try:
                conn.sendall(b"ERROR: Timeout\n")
            except:
                pass
        except Exception as e:
            bus.emit(f"{name}.connection_error", error=str(e))
            try:
                conn.sendall(f"ERROR: {str(e)}\n".encode())
            except:
                pass
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)  # Graceful shutdown
                conn.close()
            except:
                pass
            sem.release()
            if not hasattr(conn, '_closed_emitted'):
                bus.emit(f"{name}.connection_close")

    # ── Accept loop ────────────────────────────────────
    try:
        while True:
            conn, _ = server.accept()
            sem.acquire()
            threading.Thread(target=_handle, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        bus.stop()
        if teardown:
            teardown(state)
        server.close()
        if os.path.exists(args.socket):
            os.unlink(args.socket)
