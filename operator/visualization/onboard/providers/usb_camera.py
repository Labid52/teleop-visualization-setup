"""OpenCV USB-camera provider selected by index or device path."""

from __future__ import annotations

import threading
import time

import cv2

from visualization.common.models import FrameMetadata, ProviderStatus, SCHEMA_VERSION
from visualization.common.timestamps import now
from visualization.onboard.providers.base_camera import CameraFrame, CameraProvider, ProviderFailure


class UsbCameraProvider(CameraProvider):
    def __init__(self, device: int | str = 0, width: int = 1280, height: int = 720, target_fps: float = 20.0, source_id: str = "usb_camera") -> None:
        self.device = device
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self.source_id = source_id
        self._capture: cv2.VideoCapture | None = None
        self._sequence = 0
        self._state = ProviderStatus("stopped")
        self._lock = threading.Lock()

    def start(self) -> None:
        capture = cv2.VideoCapture(self.device)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.target_fps)
        if not capture.isOpened():
            capture.release()
            with self._lock:
                self._state = ProviderStatus("failed", f"cannot open camera {self.device!r}")
            raise ProviderFailure(self._state.detail)
        with self._lock:
            self._capture = capture
            self._sequence = 0
            self._state = ProviderStatus("running")

    def get_frame(self) -> CameraFrame:
        with self._lock:
            capture = self._capture
            sequence = self._sequence
        if capture is None or self.status().state != "running":
            raise ProviderFailure("USB camera is not running")
        ok, image = capture.read()
        if not ok or image is None:
            with self._lock:
                self._state = ProviderStatus("failed", "camera frame read failed")
            raise ProviderFailure(self._state.detail)
        stamp = now()
        height, width = image.shape[:2]
        metadata = FrameMetadata(SCHEMA_VERSION, self.source_id, sequence, stamp.utc, stamp.monotonic_s, width, height, self.target_fps, "running")
        with self._lock:
            self._sequence += 1
        return CameraFrame(metadata, image)

    def stop(self) -> None:
        with self._lock:
            capture, self._capture = self._capture, None
            self._state = ProviderStatus("stopped")
        if capture is not None:
            capture.release()

    def status(self) -> ProviderStatus:
        with self._lock:
            return self._state
