"""Reusable video tile with health, age, and maximize interaction."""

from __future__ import annotations

from collections import deque
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from visualization.gui.models.ui_state import CameraId, DisplayState, VideoFrameState
from visualization.gui.widgets.common import StateBadge


class CameraTile(QFrame):
    activated = Signal(object)

    def __init__(self, camera_id: CameraId, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self.title = title
        self.setObjectName("cameraTile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 145)
        self._image: QImage | None = None
        self._stream_state = DisplayState.OFFLINE
        self.latest_sequence: int | None = None
        self.latest_capture_monotonic: float | None = None
        self.rendered_frames = 0
        self.dropped_gui_frames = 0
        self._render_times: deque[float] = deque(maxlen=90)
        self._maximized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 8)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("cameraHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 7, 9, 7)
        self.name_label = QLabel(title)
        self.name_label.setObjectName("cameraName")
        self.state_badge = StateBadge("OFFLINE")
        self.focus_label = QLabel("")
        self.focus_label.setObjectName("focusLabel")
        self.maximize_button = QToolButton()
        self.maximize_button.setText("MAX")
        self.maximize_button.setToolTip(f"Maximize {title} camera")
        self.maximize_button.clicked.connect(lambda: self.activated.emit(self.camera_id))
        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.focus_label)
        header_layout.addStretch()
        header_layout.addWidget(self.state_badge)
        header_layout.addWidget(self.maximize_button)
        layout.addWidget(header)

        self.image_label = QLabel("WAITING FOR VIDEO")
        self.image_label.setObjectName("cameraImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        layout.addWidget(self.image_label, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(10, 7, 10, 0)
        footer.setSpacing(12)
        self.fps_label = QLabel("-- FPS")
        self.sequence_label = QLabel("SEQ --")
        self.age_label = QLabel("AGE --")
        self.resolution_label = QLabel("--×--")
        self.bitrate_label = QLabel("BITRATE --")
        self.record_label = QLabel("")
        for label in (self.fps_label, self.sequence_label, self.age_label, self.resolution_label, self.bitrate_label, self.record_label):
            label.setObjectName("cameraMetric")
            footer.addWidget(label)
        footer.addStretch()
        layout.addLayout(footer)

    def update_frame(self, frame: VideoFrameState) -> None:
        if frame.camera_id != self.camera_id:
            return
        image = frame.image_bgr
        if not image.flags.c_contiguous:
            image = image.copy()
        height, width, _channels = image.shape
        self._image = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_BGR888).copy()
        if self.latest_sequence is not None and frame.sequence > self.latest_sequence + 1:
            self.dropped_gui_frames += frame.sequence - self.latest_sequence - 1
        self.latest_sequence = frame.sequence
        self.latest_capture_monotonic = frame.capture_time_monotonic_s
        self.rendered_frames += 1
        self._render_times.append(time.monotonic())
        self._stream_state = frame.state
        self.state_badge.set_state(frame.state.value)
        self.age_label.setToolTip("Time since local decode; not network latency" if frame.timestamp_origin == "receiver_decode" else "Time since capture")
        self.sequence_label.setText(f"SEQ {frame.sequence}")
        self.resolution_label.setText(f"{frame.width}×{frame.height}")
        self.bitrate_label.setText("BITRATE --" if frame.bitrate_kbps is None else f"{frame.bitrate_kbps:.0f} kbps")
        self.record_label.setText("● REC" if frame.recording else "")
        self.refresh_metrics()
        self._render_pixmap()

    def set_stream_state(self, state: DisplayState) -> None:
        if state is DisplayState.LIVE and (self._image is None or self.latest_capture_monotonic is None or time.monotonic() - self.latest_capture_monotonic > 2.0):
            state = DisplayState.CONNECTING if self.latest_capture_monotonic is None else DisplayState.STALE
        self._stream_state = state
        self.state_badge.set_state(state.value)
        if state not in (DisplayState.LIVE, DisplayState.MOCK):
            self._image = None
            self.image_label.clear()
            self.image_label.setText({DisplayState.WAITING: "WAITING FOR STREAM", DisplayState.CONNECTING: "CONNECTING", DisplayState.STALE: "NO FRESH VIDEO"}.get(state, "SOURCE DISCONNECTED"))

    def refresh_metrics(self) -> None:
        now = time.monotonic()
        while self._render_times and now - self._render_times[0] > 2.0:
            self._render_times.popleft()
        fps = 0.0
        if len(self._render_times) > 1:
            fps = (len(self._render_times) - 1) / max(1e-9, self._render_times[-1] - self._render_times[0])
        self.fps_label.setText(f"{fps:4.1f} FPS")
        if self.latest_capture_monotonic is None:
            self.age_label.setText("AGE --")
        else:
            age = max(0.0, now - self.latest_capture_monotonic)
            self.age_label.setText(f"AGE {age * 1000:.0f} ms")
            if age > 2.0 and self._stream_state in (DisplayState.LIVE, DisplayState.MOCK):
                self.set_stream_state(DisplayState.STALE)

    def rendered_fps(self) -> float:
        if len(self._render_times) < 2:
            return 0.0
        return (len(self._render_times) - 1) / max(1e-9, self._render_times[-1] - self._render_times[0])

    def set_maximized(self, maximized: bool) -> None:
        self._maximized = maximized
        self.focus_label.setText("MAXIMIZED" if maximized else "")
        self.maximize_button.setText("GRID" if maximized else "MAX")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.camera_id)
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_pixmap()

    def _render_pixmap(self) -> None:
        if self._image is None:
            return
        pixmap = QPixmap.fromImage(self._image).scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
