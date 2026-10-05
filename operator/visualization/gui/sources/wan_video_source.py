"""Independent SRT/MPEG-TS/H.264 decoders behind the existing VideoSource."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import select
import subprocess
import threading
import time

import cv2
import numpy as np

from visualization.gui.models.ui_state import CameraId, DisplayState, VideoFrameState
from visualization.gui.sources.base import VideoSource
from visualization.gui.sources.bmp_stream import BmpFrameBuffer
from visualization.gui.sources.wan_config import WanCredentials
from visualization.gui.sources.decoder_selection import select_srt_decoder


@dataclass
class _Session:
    process: subprocess.Popen | None = field(default=None, repr=False)
    stop: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    buffer: BmpFrameBuffer = field(default_factory=BmpFrameBuffer, repr=False)
    state: DisplayState = DisplayState.CONNECTING
    next_attempt: float = 0.0
    backoff: float = 1.0
    process_started: float = 0.0
    last_frame: float | None = None
    first_frame: float | None = None
    frames: int = 0
    attempts: int = 0
    disconnects: int = 0
    reconnects: int = 0
    width: int = 0
    height: int = 0
    frame_times: deque = field(default_factory=lambda: deque(maxlen=90), repr=False)
    warning_chunks: int = 0


class WanVideoSource(VideoSource):
    mode = "WAN"

    def __init__(self, credentials: WanCredentials, enabled: set[CameraId] | None = None,
                 executable: str = "ffmpeg", stale_s: float = 2.0,
                 idle_timeout_s: float = 12.0, reconnect_max_s: float = 15.0,
                 startup_timeout_s: float = 45.0) -> None:
        self.credentials = credentials
        self.executable = select_srt_decoder(executable)
        self.stale_s = stale_s
        self.idle_timeout_s = idle_timeout_s
        self.startup_timeout_s = startup_timeout_s
        self.reconnect_max_s = reconnect_max_s
        selected = set(CameraId) if enabled is None else set(enabled)
        self._sessions = {role: _Session() for role in CameraId if role in selected}

    def camera_ids(self) -> tuple[CameraId, ...]:
        return tuple(self._sessions)

    def start_camera(self, camera_id: CameraId) -> None:
        session = self._sessions[camera_id]
        session.stop.clear()
        session.state = DisplayState.CONNECTING

    def decoder_command(self, camera_id: CameraId) -> list[str]:
        # Authenticated URI exists only in memory/child argv; never log this list.
        # BMP is an uncompressed LOCAL pipe format, not a WAN format change.
        return [self.executable, "-nostdin", "-hide_banner", "-loglevel", "warning",
                "-threads", "1", "-i", self.credentials.reader_uri(camera_id), "-map", "0:v:0", "-an", "-sn",
                "-vsync", "0", "-threads", "1", "-c:v", "bmp", "-pix_fmt", "bgr24",
                "-f", "image2pipe", "pipe:1"]

    def _connect(self, role: CameraId, session: _Session) -> None:
        with session.lock:
            if session.stop.is_set():
                return
            session.attempts += 1
            if session.frames:
                session.reconnects += 1
            session.buffer = BmpFrameBuffer()
            session.process_started = time.monotonic()
            session.state = DisplayState.CONNECTING
            session.process = subprocess.Popen(self.decoder_command(role),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)

    @staticmethod
    def _retire(session: _Session) -> None:
        with session.lock:
            process, session.process = session.process, None
            if process is None:
                return
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=0.4)
            for pipe in (process.stdout, process.stderr):
                if pipe:
                    pipe.close()

    def _retry(self, session: _Session) -> None:
        if session.state in (DisplayState.LIVE, DisplayState.STALE):
            session.disconnects += 1
        self._retire(session)
        session.state = DisplayState.WAITING
        session.next_attempt = time.monotonic() + session.backoff
        session.backoff = min(self.reconnect_max_s, session.backoff * 2)
        session.buffer = BmpFrameBuffer()

    def next_frame(self, camera_id: CameraId) -> VideoFrameState | None:
        session = self._sessions[camera_id]
        deadline = time.monotonic() + 0.1
        if session.stop.is_set():
            return None
        try:
            if session.process is None:
                if time.monotonic() < session.next_attempt:
                    session.stop.wait(0.1)
                    return None
                self._connect(camera_id, session)
            while not session.stop.is_set() and time.monotonic() < deadline:
                process = session.process
                if process is None:
                    return None
                encoded = session.buffer.pop()
                if encoded is not None:
                    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None:
                        raise ValueError("decoder produced an invalid frame")
                    received = time.monotonic()
                    session.frames += 1
                    session.last_frame = received
                    if session.first_frame is None:
                        session.first_frame = received
                    session.frame_times.append(received)
                    session.height, session.width = image.shape[:2]
                    session.state = DisplayState.LIVE
                    session.backoff = 1.0
                    return VideoFrameState(camera_id, image, session.frames,
                        datetime.now(timezone.utc).isoformat(timespec="milliseconds"), received,
                        session.width, session.height, 20.0, DisplayState.LIVE,
                        timestamp_origin="receiver_decode")
                if process.poll() is not None:
                    self._retry(session)
                    return None
                has_current_frame = session.last_frame is not None and session.last_frame >= session.process_started
                idle_since = session.last_frame if has_current_frame else session.process_started
                timeout = self.idle_timeout_s if has_current_frame else self.startup_timeout_s
                if time.monotonic() - idle_since > timeout:
                    self._retry(session)
                    return None
                readable, _, _ = select.select([process.stdout, process.stderr], [], [],
                    max(0, min(0.05, deadline-time.monotonic())))
                for pipe in readable:
                    data = os.read(pipe.fileno(), 1024 * 1024 if pipe is process.stdout else 65536)
                    if not data:
                        continue
                    if pipe is process.stdout:
                        session.buffer.append(data)
                    else:
                        # FFmpeg stderr may contain a credential URI. Retain no text.
                        session.warning_chunks += 1
            return None
        except (OSError, ValueError, subprocess.SubprocessError):
            if not session.stop.is_set():
                self._retry(session)
            return None

    def camera_status(self, camera_id: CameraId) -> tuple[DisplayState, str]:
        session = self._sessions[camera_id]
        state = session.state
        if state is DisplayState.LIVE and time.monotonic() - session.last_frame > self.stale_s:
            state = DisplayState.STALE
        detail = {DisplayState.CONNECTING: "Connecting to stream", DisplayState.WAITING: "Waiting for stream; automatic retry",
                  DisplayState.STALE: "No fresh decoded frame", DisplayState.LIVE: "WAN stream decoded",
                  DisplayState.DISCONNECTED: "Reader stopped"}.get(state, "")
        return state, detail

    def stop_camera(self, camera_id: CameraId) -> None:
        session = self._sessions[camera_id]
        session.stop.set()
        self._retire(session)
        session.state = DisplayState.DISCONNECTED

    def diagnostics(self) -> dict[str, dict]:
        result = {}
        for role, session in self._sessions.items():
            times = tuple(session.frame_times)
            result[role.value] = {"state": self.camera_status(role)[0].value,
                "decoder_executable": self.executable,
                "frames_decoded": session.frames, "connection_attempts": session.attempts,
                "disconnects": session.disconnects, "reconnects": session.reconnects,
                "resolution": [session.width, session.height], "buffer_bytes": len(session.buffer),
                "maximum_buffer_bytes": session.buffer.maximum_bytes,
                "decoded_fps": (len(times)-1)/(times[-1]-times[0]) if len(times)>1 else 0,
                "first_frame_monotonic_s": session.first_frame,
                "decoder_warning_chunks": session.warning_chunks}
        return result
