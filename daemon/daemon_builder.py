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
import os
import socket
import sys
import threading

from eventbus import EventBus


def run_daemon(
    name,
    *,
    default_socket,
    default_event_socket=None,
    setup,
    handle_client,
    teardown=None,
    max_connections=5,
    startup_timeout=60,
):
    """Run a Unix socket daemon.

    Parameters
    ----------
    name : str
        Human-readable daemon name (printed in logs).
    default_socket : str
        Default Unix socket path.
    default_event_socket : str or None
        Default event bus socket path (None to disable events).
    setup : callable[[], any]
        Called once before the accept loop. Return value is passed to
        handle_client and teardown as `state`.
    handle_client : callable[[socket, any, EventBus|None], None]
        Called in a new thread per connection.
        Signature: (conn, state, bus).
    teardown : callable[[any], None] or None
        Called once on shutdown with the state object.
    max_connections : int
        Max concurrent client threads (passed to listen() and Semaphore).
    startup_timeout : int
        Maximum seconds to wait for setup() before giving up.
        The caller (bash wait_for_socket) uses this to know how long to poll.
    """
    ready_file = default_socket + ".ready"

    parser = argparse.ArgumentParser(description=f"{name} daemon")
    parser.add_argument("--socket", default=default_socket,
                        help=f"Unix socket path (default: {default_socket})")
    parser.add_argument("--event-socket", default=default_event_socket,
                        help=f"Event bus socket path (default: {default_event_socket})")
    parser.add_argument("--startup-timeout", type=int, default=startup_timeout,
                        help="Seconds allowed for setup()")
    parser.add_argument("--ready-file", default=ready_file,
                        help="Path written after setup() completes")
    args = parser.parse_args()

    if os.path.exists(args.socket):
        os.unlink(args.socket)
    if os.path.exists(args.ready_file):
        os.unlink(args.ready_file)

    # ── Event bus ──────────────────────────────────────
    bus = None
    if default_event_socket:
        bus = EventBus(args.event_socket)
        bus.start()

    # Create socket early so bash sees it immediately
    sem = threading.Semaphore(max_connections)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(args.socket)
    os.chmod(args.socket, 0o777)

    # ── Setup (with timeout) ───────────────────────────
    timer = threading.Timer(args.startup_timeout, lambda: os._exit(1))
    timer.start()
    try:
      state = setup()
    finally:
      timer.cancel()

    # Signal readiness to bash
    with open(args.ready_file, "w") as f:
        f.write("ready")
    server.listen(max_connections)
    print(f"{name} daemon ready on {args.socket}", flush=True)
    if bus:
        print(f"  events on {args.event_socket}", flush=True)

    def _handle(conn):
        try:
            handle_client(conn, state, bus)
        except Exception:
            pass
        finally:
            sem.release()

    # ── Accept loop ────────────────────────────────────
    try:
        while True:
            conn, _ = server.accept()
            sem.acquire()
            threading.Thread(target=_handle, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        if bus:
            bus.stop()
        if teardown:
            teardown(state)
        server.close()
        if os.path.exists(args.socket):
            os.unlink(args.socket)
        if os.path.exists(args.ready_file):
            os.unlink(args.ready_file)
