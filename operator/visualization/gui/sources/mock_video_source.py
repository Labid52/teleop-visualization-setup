"""Four distinct camera feeds built on the Level 3A mock provider."""

from __future__ import annotations

import cv2
import numpy as np

from visualization.gui.models.ui_state import CameraId, DisplayState, VideoFrameState
from visualization.gui.sources.base import VideoSource
from visualization.onboard.providers.mock_camera import MockCameraProvider


class MockVideoSource(VideoSource):
    mode = "MOCK"
    DEFAULT_FPS = {
        CameraId.FRONT: 20.0,
        CameraId.LEFT: 18.0,
        CameraId.RIGHT: 18.0,
        CameraId.CABIN: 16.0,
    }

    def __init__(self, width: int = 640, height: int = 360, fps: dict[CameraId, float] | None = None, enabled: set[CameraId] | None = None) -> None:
        rates = {**self.DEFAULT_FPS, **(fps or {})}
        selected = set(CameraId) if enabled is None else set(enabled)
        self._providers = {
            camera_id: MockCameraProvider(f"{camera_id.value}_camera", width, height, rates[camera_id])
            for camera_id in CameraId if camera_id in selected
        }

    def camera_ids(self) -> tuple[CameraId, ...]:
        return tuple(self._providers)

    def start_camera(self, camera_id: CameraId) -> None:
        self._providers[camera_id].start()

    def next_frame(self, camera_id: CameraId) -> VideoFrameState:
        raw = self._providers[camera_id].get_frame()
        image = raw.image.copy()
        self._style(camera_id, raw.metadata.frame_sequence, image)
        metadata = raw.metadata
        return VideoFrameState(camera_id, image, metadata.frame_sequence, metadata.capture_time_utc, metadata.capture_time_monotonic_s, metadata.width, metadata.height, metadata.fps_target, DisplayState.MOCK)

    def stop_camera(self, camera_id: CameraId) -> None:
        self._providers[camera_id].stop()

    @staticmethod
    def _style(camera_id: CameraId, sequence: int, image: np.ndarray) -> None:
        height, width = image.shape[:2]
        overlay = image.copy()
        colors = {
            CameraId.FRONT: (224, 177, 58),
            CameraId.LEFT: (90, 190, 255),
            CameraId.RIGHT: (180, 115, 255),
            CameraId.CABIN: (120, 220, 150),
        }
        color = colors[camera_id]
        if camera_id is CameraId.FRONT:
            horizon = int(height * 0.45)
            cv2.line(overlay, (0, horizon), (width, horizon), color, 2)
            offset = sequence % 40
            for y in range(horizon + offset, height, 40):
                scale = (y - horizon) / max(1, height - horizon)
                half = int(20 + scale * width * 0.25)
                cv2.line(overlay, (width // 2 - half, y), (width // 2 - half - 15, min(height - 1, y + 25)), (235, 235, 235), 3)
                cv2.line(overlay, (width // 2 + half, y), (width // 2 + half + 15, min(height - 1, y + 25)), (235, 235, 235), 3)
        elif camera_id in (CameraId.LEFT, CameraId.RIGHT):
            direction = -1 if camera_id is CameraId.LEFT else 1
            x = int((sequence * 9) % (width + 120)) - 60
            if direction < 0:
                x = width - x
            for index in range(4):
                center = (int(x + direction * index * 75), int(height * (0.3 + 0.14 * index)))
                cv2.circle(overlay, center, 24, color, 3)
                cv2.line(overlay, center, (center[0] + direction * 35, center[1]), color, 3)
        else:
            center = (width // 2, int(height * 0.55))
            angle = np.sin(sequence / 15.0) * 70.0
            cv2.circle(overlay, center, int(height * 0.22), color, 5)
            radians = np.radians(angle)
            end = (int(center[0] + np.sin(radians) * height * 0.18), int(center[1] - np.cos(radians) * height * 0.18))
            cv2.line(overlay, center, end, color, 6)
            cv2.rectangle(overlay, (int(width * 0.18), int(height * 0.75)), (int(width * 0.28), int(height * 0.94)), color, 3)
            cv2.rectangle(overlay, (int(width * 0.72), int(height * 0.75)), (int(width * 0.82), int(height * 0.94)), color, 3)
        cv2.addWeighted(overlay, 0.75, image, 0.25, 0, image)
        cv2.rectangle(image, (0, height - 48), (width, height), (10, 15, 22), -1)
        cv2.putText(image, f"{camera_id.value.upper()} CAMERA  //  MOCK", (18, height - 17), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
