"""Source contracts isolate widgets from local and future WAN transports."""

from __future__ import annotations

from abc import ABC, abstractmethod

from visualization.gui.models.ui_state import CameraId, DisplayState, OperatorState, TelemetryState, VideoFrameState


class VideoSource(ABC):
    def camera_status(self, camera_id):
        return DisplayState.MOCK, "mock source active"

    @abstractmethod
    def camera_ids(self) -> tuple[CameraId, ...]: ...

    @abstractmethod
    def start_camera(self, camera_id: CameraId) -> None: ...

    @abstractmethod
    def next_frame(self, camera_id: CameraId) -> VideoFrameState | None: ...

    @abstractmethod
    def stop_camera(self, camera_id: CameraId) -> None: ...


class TelemetrySource(ABC):
    def status(self):
        return DisplayState.MOCK

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def get_latest(self) -> TelemetryState | None: ...

    @abstractmethod
    def stop(self) -> None: ...


class OperatorStateSource(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def get_latest(self) -> OperatorState: ...

    @abstractmethod
    def stop(self) -> None: ...
