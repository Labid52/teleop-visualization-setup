"""Compact component-state and onboard-health panel."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel

from visualization.gui.models.ui_state import DisplayState, HealthState
from visualization.gui.widgets.common import PanelFrame, StateBadge, value_row


class SystemStatusPanel(PanelFrame):
    NAMES = ("CONTROL LINK", "OCI CONTROL RELAY", "FRONT CAMERA", "LEFT CAMERA", "RIGHT CAMERA", "CABIN CAMERA", "GPS", "TELEMETRY", "ONBOARD COMPUTER", "GUI")

    def __init__(self, parent=None) -> None:
        super().__init__("SYSTEM STATUS", "CONNECTIONS / HEALTH", parent)
        grid = QGridLayout()
        self.badges: dict[str, StateBadge] = {}
        for index, name in enumerate(self.NAMES):
            label = QLabel(name)
            label.setObjectName("metricLabel")
            badge = StateBadge("MOCK" if name not in ("CONTROL LINK", "OCI CONTROL RELAY") else "--")
            self.badges[name] = badge
            row, column = divmod(index, 2)
            box = PanelFrame()
            box.setObjectName("statusCard")
            box.outer.setContentsMargins(7, 5, 7, 5)
            box.outer.addWidget(label)
            box.outer.addWidget(badge)
            grid.addWidget(box, row, column)
        self.outer.addLayout(grid)
        self.values: dict[str, QLabel] = {}
        for key, label in (("cpu", "CPU"), ("memory", "Memory"), ("uptime", "Session uptime"), ("video", "Video pipeline"), ("telemetry", "Telemetry rate"), ("camera", "Camera FPS"), ("gps", "GPS rate")):
            row, value = value_row(label)
            self.values[key] = value
            self.outer.addWidget(row)

    def set_component(self, name: str, state: DisplayState) -> None:
        if name in self.badges:
            self.badges[name].set_state(state.value)

    def update_health(self, health: HealthState) -> None:
        self.badges["ONBOARD COMPUTER"].set_state(health.state.value)
        self.values["cpu"].setText("--" if health.cpu_percent is None else f"{health.cpu_percent:.1f}%")
        self.values["memory"].setText("--" if health.memory_percent is None else f"{health.memory_percent:.1f}%")
        hours, remainder = divmod(int(health.uptime_s or 0), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.values["uptime"].setText("--" if health.uptime_s is None else f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.values["video"].setText(health.video_pipeline_state.value)
        self.values["telemetry"].setText("--" if health.telemetry_rate_hz is None else f"{health.telemetry_rate_hz:.1f} Hz")
        self.values["camera"].setText("--" if health.camera_fps is None else f"{health.camera_fps:.1f} FPS")
        self.values["gps"].setText("--" if health.gps_rate_hz is None else f"{health.gps_rate_hz:.1f} Hz")
