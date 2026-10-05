"""Bounded operator event strip."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import QListWidget

from visualization.gui.widgets.common import PanelFrame


class EventLogPanel(PanelFrame):
    def __init__(self, max_events: int = 80, parent=None) -> None:
        super().__init__("EVENTS", "RECENT VISUALIZATION MESSAGES", parent)
        self.max_events = max_events
        self.list = QListWidget()
        self.list.setObjectName("eventList")
        self.list.setMaximumHeight(125)
        self.outer.addWidget(self.list)

    def add_event(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.list.insertItem(0, f"{timestamp}Z   {message}")
        while self.list.count() > self.max_events:
            self.list.takeItem(self.list.count() - 1)
