"""Prominent speed display retaining SI state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpeedWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.speed_mps = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.mph = QLabel("0.0")
        self.mph.setObjectName("speedValue")
        self.mph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit = unit = QLabel("MPH  /  MOCK")
        unit.setObjectName("speedUnit")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.si = QLabel("0.00 m/s")
        self.si.setObjectName("speedSI")
        self.si.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.mph)
        layout.addWidget(unit)
        layout.addWidget(self.si)

    def set_speed(self, speed_mps: float | None) -> None:
        if speed_mps is None:
            self.speed_mps = None
            self.mph.setText("--")
            self.si.setText("-- m/s")
            return
        self.speed_mps = max(0.0, speed_mps)
        self.mph.setText(f"{self.speed_mps * 2.236936:.1f}")
        self.si.setText(f"{self.speed_mps:.2f} m/s")
