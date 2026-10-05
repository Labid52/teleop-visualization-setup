"""Compact current-rate and mode strip."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from visualization.gui.models.ui_state import CameraId


class BottomBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 5, 14, 5)
        self.labels = {}
        items = (("control", "Control: --"), (CameraId.FRONT.value, "Front: --"), (CameraId.LEFT.value, "Left: --"), (CameraId.RIGHT.value, "Right: --"), (CameraId.CABIN.value, "Cabin: --"), ("gps", "GPS: --"), ("telemetry", "Telemetry: --"), ("dropped", "Dropped: 0"))
        for key, text in items:
            label = QLabel(text)
            label.setObjectName("bottomMetric")
            self.labels[key] = label
            layout.addWidget(label)
        layout.addStretch()
        self.mode_label = mode = QLabel("MODE  MOCK")
        mode.setObjectName("modePill")
        layout.addWidget(mode)

    def update_camera(self, camera_id: CameraId, fps: float) -> None:
        self.labels[camera_id.value].setText(f"{camera_id.value.title()}: {fps:.1f} FPS")

    def update_rates(self, gps_hz: float, telemetry_hz: float, dropped: int) -> None:
        self.labels["gps"].setText(f"GPS: {gps_hz:.1f} Hz")
        self.labels["telemetry"].setText(f"Telemetry: {telemetry_hz:.1f} Hz")
        self.labels["dropped"].setText(f"Dropped: {dropped}")
