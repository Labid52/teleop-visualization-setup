"""Display-only normalized steering gauge."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SteeringWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.value = 0.0
        self.setMinimumHeight(85)

    def set_value(self, value: float) -> None:
        self.value = max(-1.0, min(1.0, value))
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 18
        center_x = self.width() / 2
        y = self.height() * 0.62
        painter.setPen(QPen(QColor("#24364a"), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(margin, int(y), self.width() - margin, int(y))
        painter.setPen(QPen(QColor("#71849a"), 2))
        painter.drawLine(int(center_x), int(y - 15), int(center_x), int(y + 15))
        x = center_x + self.value * (self.width() / 2 - margin)
        color = QColor("#45b8ff") if abs(self.value) < 0.75 else QColor("#f3b75b")
        painter.setPen(QPen(color, 4))
        painter.setBrush(QColor("#dcecff"))
        painter.drawEllipse(QPointF(x, y), 9, 9)
        painter.setPen(QColor("#edf5ff"))
        painter.drawText(self.rect().adjusted(0, 3, 0, -42), Qt.AlignmentFlag.AlignCenter, f"{self.value:+.3f}")
        painter.setPen(QColor("#63778c"))
        painter.drawText(margin, self.height() - 7, "LEFT")
        painter.drawText(self.width() - margin - 40, self.height() - 7, "RIGHT")
