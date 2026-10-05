"""Receive loopback diagnostics, optionally previewing decoded frames."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import threading
import time
from typing import Any

import cv2
import numpy as np


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("diagnostic connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class DiagnosticReceiver:
    def __init__(self, host: str = "127.0.0.1", telemetry_port: int = 8765, video_port: int = 8766, preview: bool = False, video_consumer_delay_s: float = 0.0) -> None:
        if host != "127.0.0.1":
            raise ValueError("Level 3A receiver connects only to 127.0.0.1")
        self.host = host
        self.telemetry_port = telemetry_port
        self.video_port = video_port
        self.preview = preview
        self.video_consumer_delay_s = video_consumer_delay_s
        self.telemetry_received = 0
        self.frames_received = 0
        self.frames_decoded = 0
        self.latest_telemetry: dict[str, Any] | None = None
        self.latest_frame_metadata: dict[str, Any] | None = None
        self.latest_frame: Any = None
        self.errors: list[str] = []
        self._started_at = 0.0
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._sockets: list[socket.socket] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._stop.clear()
        self._threads = [
            threading.Thread(target=self._telemetry_loop, name="viz-diagnostic-telemetry", daemon=True),
            threading.Thread(target=self._video_loop, name="viz-diagnostic-video", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def _connect(self, port: int) -> socket.socket:
        while not self._stop.is_set():
            try:
                sock = socket.create_connection((self.host, port), timeout=0.5)
                sock.settimeout(0.5)
                with self._lock:
                    self._sockets.append(sock)
                return sock
            except OSError:
                self._stop.wait(0.1)
        raise ConnectionError("receiver stopping")

    def _telemetry_loop(self) -> None:
        try:
            sock = self._connect(self.telemetry_port)
            buffer = b""
            while not self._stop.is_set():
                try:
                    data = sock.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self.latest_telemetry = json.loads(line.decode("utf-8"))
                    self.telemetry_received += 1
        except (ConnectionError, OSError, json.JSONDecodeError) as exc:
            if not self._stop.is_set():
                self.errors.append(f"telemetry: {exc}")

    def _video_loop(self) -> None:
        try:
            sock = self._connect(self.video_port)
            while not self._stop.is_set():
                header_size = struct.unpack("!I", _recv_exact(sock, 4))[0]
                metadata = json.loads(_recv_exact(sock, header_size).decode("utf-8"))
                image_size = struct.unpack("!I", _recv_exact(sock, 4))[0]
                jpeg = _recv_exact(sock, image_size)
                self.frames_received += 1
                self.latest_frame_metadata = metadata
                image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    self.frames_decoded += 1
                    self.latest_frame = image
                    if self.preview:
                        cv2.imshow("Level 3A diagnostic video", image)
                        cv2.waitKey(1)
                if self.video_consumer_delay_s:
                    self._stop.wait(self.video_consumer_delay_s)
        except (ConnectionError, OSError, json.JSONDecodeError, struct.error) as exc:
            if not self._stop.is_set():
                self.errors.append(f"video: {exc}")

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            sockets, self._sockets = self._sockets, []
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        for thread in self._threads:
            thread.join(timeout=2.0)
        if self.preview:
            cv2.destroyAllWindows()

    def rates(self) -> tuple[float, float]:
        elapsed = max(1e-9, time.monotonic() - self._started_at)
        return self.frames_received / elapsed, self.telemetry_received / elapsed

    def snapshot_text(self) -> str:
        video_hz, telemetry_hz = self.rates()
        telemetry = self.latest_telemetry or {}
        gps = telemetry.get("gps") or {}
        camera = telemetry.get("camera") or {}
        system = telemetry.get("system") or {}
        freshness = None
        if telemetry.get("timestamp_monotonic_s") is not None:
            freshness = time.monotonic() - telemetry["timestamp_monotonic_s"]
        return (
            f"video={video_hz:.2f}Hz telemetry={telemetry_hz:.2f}Hz "
            f"frame={camera.get('latest_frame_sequence')} gps={gps.get('sequence')} "
            f"dropped={camera.get('frames_dropped_locally')} freshness_s={freshness!r} "
            f"cpu={system.get('cpu_percent')} memory={system.get('memory_percent')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Level 3A local diagnostic receiver")
    parser.add_argument("--telemetry-port", type=int, default=8765)
    parser.add_argument("--video-port", type=int, default=8766)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--duration", type=float, default=0.0)
    args = parser.parse_args()
    receiver = DiagnosticReceiver(telemetry_port=args.telemetry_port, video_port=args.video_port, preview=args.preview)
    receiver.start()
    started = time.monotonic()
    try:
        while args.duration <= 0 or time.monotonic() - started < args.duration:
            time.sleep(1.0)
            print(receiver.snapshot_text())
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
