"""Console identity, mode, status, clocks, and screenshot action."""

from __future__ import annotations

from datetime import datetime, timezone
import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from visualization.gui.widgets.common import StateBadge


class TopBar(QFrame):
    screenshot_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.started_at = time.monotonic()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 10)
        title_box = QVBoxLayout()
        eyebrow = QLabel("MILA · INTERNET TELEOPERATION")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("REMOTE VEHICLE OPERATOR CONSOLE")
        title.setObjectName("appTitle")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        layout.addLayout(title_box)
        layout.addSpacing(30)
        self.badges = {}
        for name, state in (("CONTROL", "--"), ("VIDEO", "MOCK"), ("GPS", "MOCK"), ("SYSTEM", "MOCK")):
            box = QVBoxLayout()
            label = QLabel(name)
            label.setObjectName("metricLabel")
            badge = StateBadge(state)
            self.badges[name] = badge
            box.addWidget(label)
            box.addWidget(badge)
            layout.addLayout(box)
        layout.addStretch()
        self.mode_label = mode = QLabel("VISUALIZATION MODE  ·  MOCK")
        mode.setObjectName("modePill")
        layout.addWidget(mode)
        self.clock = QLabel()
        self.clock.setObjectName("clock")
        layout.addWidget(self.clock)
        capture = QPushButton("CAPTURE  F12")
        capture.setObjectName("captureButton")
        capture.clicked.connect(self.screenshot_requested)
        layout.addWidget(capture)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_clock)
        self.timer.start(250)
        self._refresh_clock()

    def _refresh_clock(self) -> None:
        utc = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M:%S UTC")
        elapsed = int(time.monotonic() - self.started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.clock.setText(f"{utc}\nSESSION  {hours:02d}:{minutes:02d}:{seconds:02d}")
