"""Display-only normalized pedal bar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class PedalWidget(QWidget):
    def __init__(self, name: str, accent: str, parent=None) -> None:
        super().__init__(parent)
        self.value = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QLabel(name.upper())
        header.setObjectName("metricLabel")
        self.percent = QLabel("0%")
        self.percent.setObjectName("pedalValue")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setProperty("accent", accent)
        layout.addWidget(header)
        layout.addWidget(self.percent)
        layout.addWidget(self.bar)

    def set_value(self, value: float) -> None:
        self.value = max(0.0, min(1.0, value))
        self.percent.setText(f"{self.value * 100:.0f}%")
        self.bar.setValue(round(self.value * 1000))
