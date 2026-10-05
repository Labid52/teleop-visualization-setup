"""Painted compass and heading indicator."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class CompassWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.heading_deg = 0.0
        self.setMinimumSize(130, 130)

    def set_heading(self, heading_deg: float | None) -> None:
        self.heading_deg = None if heading_deg is None else heading_deg % 360.0
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = side * 0.39
        painter.setPen(QPen(QColor("#26384d"), 7))
        painter.setBrush(QColor("#0b121b"))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor("#6f8298"), 1))
        for degree in range(0, 360, 30):
            angle = math.radians(degree - 90)
            inner = radius * (0.78 if degree % 90 else 0.68)
            painter.drawLine(QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner), QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius))
        painter.setFont(QFont("Sans Serif", max(8, int(side * 0.075)), QFont.Weight.DemiBold))
        painter.setPen(QColor("#d9e5f2"))
        for label, degree in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
            angle = math.radians(degree - 90)
            position = QPointF(center.x() + math.cos(angle) * radius * 0.56, center.y() + math.sin(angle) * radius * 0.56)
            painter.drawText(int(position.x() - 12), int(position.y() - 10), 24, 20, Qt.AlignmentFlag.AlignCenter, label)
        painter.save()
        painter.translate(center)
        painter.rotate(self.heading_deg or 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#45b8ff"))
        if self.heading_deg is not None:
            painter.drawPolygon(QPolygonF([QPointF(0, -radius * 0.67), QPointF(-9, 10), QPointF(0, 3), QPointF(9, 10)]))
        painter.restore()
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Sans Serif", max(10, int(side * 0.09)), QFont.Weight.Bold))
        painter.drawText(self.rect().adjusted(0, int(side * 0.62), 0, 0), Qt.AlignmentFlag.AlignHCenter, "--" if self.heading_deg is None else f"{self.heading_deg:03.0f}°")
