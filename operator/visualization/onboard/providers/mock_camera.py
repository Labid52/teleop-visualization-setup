"""Deterministic synthetic camera with a moving freeze-detection pattern."""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from visualization.common.models import FrameMetadata, ProviderStatus, SCHEMA_VERSION
from visualization.common.timestamps import now
from visualization.onboard.providers.base_camera import CameraFrame, CameraProvider, ProviderFailure


class MockCameraProvider(CameraProvider):
    def __init__(
        self,
        source_id: str = "mock_camera",
        width: int = 640,
        height: int = 360,
        target_fps: float = 20.0,
        fail_after_frames: int | None = None,
    ) -> None:
        if width <= 0 or height <= 0 or target_fps <= 0:
            raise ValueError("camera dimensions and target_fps must be positive")
        self.source_id = source_id
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.fail_after_frames = fail_after_frames
        self._sequence = 0
        self._next_frame_at = 0.0
        self._state = ProviderStatus("stopped")
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._sequence = 0
            self._next_frame_at = time.monotonic()
            self._state = ProviderStatus("running")

    def get_frame(self) -> CameraFrame:
        with self._lock:
            if self._state.state != "running":
                raise ProviderFailure(self._state.detail or "mock camera is not running")
            sequence = self._sequence
            if self.fail_after_frames is not None and sequence >= self.fail_after_frames:
                self._state = ProviderStatus("failed", "simulated camera failure")
                raise ProviderFailure(self._state.detail)
            deadline = self._next_frame_at

        delay = deadline - time.monotonic()
        if delay > 0:
            time.sleep(delay)

        stamp = now()
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        image[:, :, 0] = np.linspace(20, 160, self.width, dtype=np.uint8)
        image[:, :, 1] = (sequence * 7) % 150
        x = int((sequence * 13) % max(1, self.width))
        y = int(self.height / 2 + (self.height / 3) * np.sin(sequence / 7.0))
        cv2.circle(image, (x, y), max(8, min(self.width, self.height) // 18), (0, 255, 255), -1)
        cv2.line(image, (x, 0), (x, self.height - 1), (255, 255, 255), 2)
        labels = (
            f"source={self.source_id}",
            f"frame={sequence}",
            f"utc={stamp.utc}",
            f"monotonic={stamp.monotonic_s:.3f}",
        )
        for row, label in enumerate(labels, start=1):
            cv2.putText(image, label, (15, 28 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        metadata = FrameMetadata(
            schema_version=SCHEMA_VERSION,
            source_id=self.source_id,
            frame_sequence=sequence,
            capture_time_utc=stamp.utc,
            capture_time_monotonic_s=stamp.monotonic_s,
            width=self.width,
            height=self.height,
            fps_target=self.target_fps,
            provider_status="running",
        )
        with self._lock:
            self._sequence += 1
            period = 1.0 / self.target_fps
            self._next_frame_at = max(self._next_frame_at + period, time.monotonic())
        return CameraFrame(metadata, image)

    def stop(self) -> None:
        with self._lock:
            self._state = ProviderStatus("stopped")

    def status(self) -> ProviderStatus:
        with self._lock:
            return self._state
