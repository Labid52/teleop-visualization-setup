"""Offline schematic map with GPS metrics, compass, and speed."""

from __future__ import annotations

from collections import deque
import math
import time

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QWidget

from visualization.gui.models.ui_state import GPSState, DisplayState
from visualization.gui.widgets.common import PanelFrame, StateBadge, value_row
from visualization.gui.widgets.compass_widget import CompassWidget
from visualization.gui.widgets.speed_widget import SpeedWidget


class SchematicMap(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self._track: deque[tuple[float, float]] = deque(maxlen=150)
        self.heading_deg = 0.0

    def update_position(self, latitude: float, longitude: float, heading_deg: float | None) -> None:
        self._track.append((latitude, longitude))
        self.heading_deg = heading_deg
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#09111a"))
        grid = 34
        painter.setPen(QPen(QColor("#172839"), 1))
        for x in range(0, self.width(), grid):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid):
            painter.drawLine(0, y, self.width(), y)
        painter.setPen(QPen(QColor("#22384e"), 3))
        painter.drawLine(0, int(self.height() * 0.7), self.width(), int(self.height() * 0.28))
        painter.drawLine(int(self.width() * 0.18), self.height(), int(self.width() * 0.68), 0)
        if self._track:
            origin_lat, origin_lon = self._track[0]
            scale = 1_800_000.0
            points = [QPointF(self.width() / 2 + (lon - origin_lon) * scale, self.height() / 2 - (lat - origin_lat) * scale) for lat, lon in self._track]
            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.setPen(QPen(QColor("#45b8ff"), 3))
            painter.drawPath(path)
            position = points[-1]
        else:
            painter.setPen(QColor("#5f7388"))
            painter.drawText(10, 20, "NO VALID POSITION / LOCAL SCHEMATIC")
            return
        painter.save()
        painter.translate(position)
        painter.rotate(self.heading_deg or 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#50e3a4"))
        if self.heading_deg is None:
            painter.drawEllipse(QPointF(0, 0), 7, 7)
        else:
            painter.drawPolygon(QPolygonF([QPointF(0, -14), QPointF(-9, 10), QPointF(0, 6), QPointF(9, 10)]))
        painter.restore()
        painter.setPen(QColor("#5f7388"))
        painter.drawText(10, 20, "LOCAL SCHEMATIC  /  NO MAP SERVICE")


class GPSPanel(PanelFrame):
    def __init__(self, parent=None) -> None:
        super().__init__("POSITION & MOTION", "GPS / OFFLINE MAP", parent)
        self.state_badge = StateBadge("MOCK")
        self.outer.itemAt(0).layout().addWidget(self.state_badge)
        self.map = SchematicMap()
        self.outer.addWidget(self.map, 2)
        overview = QHBoxLayout()
        self.compass = CompassWidget()
        self.speed = SpeedWidget()
        overview.addWidget(self.compass, 1)
        overview.addWidget(self.speed, 1)
        self.outer.addLayout(overview)
        details = QGridLayout()
        self.values: dict[str, QLabel] = {}
        for index, (key, label) in enumerate((("lat", "Latitude"), ("lon", "Longitude"), ("fix", "Fix"), ("sat", "Satellites"), ("accuracy", "Accuracy"), ("age", "Update age"), ("rate", "Update rate"))):
            row, value = value_row(label)
            self.values[key] = value
            details.addWidget(row, index, 0)
        self.outer.addLayout(details)
        self.last_sequence: int | None = None
        self.update_count = 0
        self.started_at = time.monotonic()

    def update_gps(self, gps: GPSState) -> None:
        if not gps.published:
            self.set_stream_state(DisplayState.NO_DATA)
            self.values["fix"].setText("GNSS NOT PUBLISHED")
            self.state_badge.setToolTip("Telemetry is connected, but the publisher supplied no GNSS section")
            return
        self.state_badge.setToolTip("")
        self.last_sequence = gps.sequence
        self.update_count += 1
        self.state_badge.set_state(gps.state.value)
        if gps.fix_valid and gps.latitude is not None and gps.longitude is not None and gps.state is not DisplayState.STALE:
            self.map.update_position(gps.latitude, gps.longitude, gps.heading_deg)
        else:
            self.map._track.clear()
            self.map.update()
        self.compass.set_heading(gps.heading_deg)
        self.compass.setToolTip("Heading source: " + gps.heading_source)
        self.speed.set_speed(gps.speed_mps)
        self.values["lat"].setText("--" if gps.latitude is None else f"{gps.latitude:.6f}°")
        self.values["lon"].setText("--" if gps.longitude is None else f"{gps.longitude:.6f}°")
        self.values["fix"].setText("VALID" if gps.fix_valid else "INVALID")
        self.values["sat"].setText("--" if gps.satellites is None else str(gps.satellites))
        self.values["accuracy"].setText("--" if gps.horizontal_accuracy_m is None else f"±{gps.horizontal_accuracy_m:.1f} m")
        self.values["age"].setText(f"{max(0.0, time.monotonic() - gps.timestamp_monotonic_s) * 1000:.0f} ms")
        elapsed = max(1e-9, time.monotonic() - self.started_at)
        self.values["rate"].setText(f"{self.update_count / elapsed:.1f} Hz")

    def gps_rate(self) -> float:
        return self.update_count / max(1e-9, time.monotonic() - self.started_at)

    def set_stream_state(self, state):
        self.state_badge.set_state(state.value)
        if state not in (DisplayState.LIVE, DisplayState.MOCK):
            self.speed.set_speed(None)
            self.compass.set_heading(None)
            self.map._track.clear()
            self.map.update()
            for value in self.values.values():
                value.setText("--")
