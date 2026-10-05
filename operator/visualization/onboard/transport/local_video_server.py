"""Length-prefixed JPEG frames over loopback TCP for Level 3A diagnostics."""

from __future__ import annotations

import json
import socket
import struct
import threading
from dataclasses import asdict

from visualization.common.bounded_queue import DropOldestQueue, QueueClosed
from visualization.common.models import EncodedFrame


class LocalVideoServer:
    def __init__(self, queue: DropOldestQueue[EncodedFrame], host: str = "127.0.0.1", port: int = 8766) -> None:
        if host != "127.0.0.1":
            raise ValueError("Level 3A diagnostic server must bind to 127.0.0.1")
        self.queue = queue
        self.host = host
        self.port = port
        self.connections = 0
        self.frames_sent = 0
        self.disconnects = 0
        self._stop = threading.Event()
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.ready = threading.Event()
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="viz-video-transport", daemon=True)
        self._thread.start()
        if not self.ready.wait(3.0):
            raise RuntimeError("video server did not start")
        if self.error:
            raise RuntimeError(f"video server failed: {self.error}")

    def _run(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host, self.port))
        except OSError as exc:
            self.error = str(exc)
            self.ready.set()
            server.close()
            return
        self.port = server.getsockname()[1]
        server.listen(2)
        server.settimeout(0.2)
        self._server = server
        self.ready.set()
        try:
            while not self._stop.is_set():
                try:
                    client, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        return
                    raise
                self.connections += 1
                client.settimeout(0.5)
                try:
                    while not self._stop.is_set():
                        try:
                            frame = self.queue.get(timeout=0.2)
                        except TimeoutError:
                            continue
                        header = json.dumps(asdict(frame.metadata), separators=(",", ":")).encode("utf-8")
                        client.sendall(struct.pack("!I", len(header)) + header + struct.pack("!I", len(frame.jpeg_bytes)) + frame.jpeg_bytes)
                        self.frames_sent += 1
                except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError):
                    self.disconnects += 1
                except QueueClosed:
                    return
                finally:
                    client.close()
        finally:
            server.close()

    def stop(self) -> None:
        self._stop.set()
        if self._server:
            try:
                self._server.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._server.close()
        if self._thread:
            self._thread.join(timeout=3.0)

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())
