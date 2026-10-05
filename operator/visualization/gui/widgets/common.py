"""Shared panel and status components."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PanelFrame(QFrame):
    def __init__(self, title: str = "", eyebrow: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(14, 12, 14, 12)
        self.outer.setSpacing(9)
        if title or eyebrow:
            header = QHBoxLayout()
            title_box = QVBoxLayout()
            title_box.setSpacing(0)
            if eyebrow:
                eyebrow_label = QLabel(eyebrow.upper())
                eyebrow_label.setObjectName("eyebrow")
                title_box.addWidget(eyebrow_label)
            if title:
                title_label = QLabel(title)
                title_label.setObjectName("panelTitle")
                title_box.addWidget(title_label)
            header.addLayout(title_box)
            header.addStretch()
            self.outer.addLayout(header)


class StateBadge(QLabel):
    def __init__(self, text: str = "--", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("stateBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(text)

    def set_state(self, state: str) -> None:
        self.setText(state.upper())
        self.setProperty("state", state.upper())
        self.style().unpolish(self)
        self.style().polish(self)


def value_row(label: str, value: str = "--") -> tuple[QWidget, QLabel]:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    name = QLabel(label.upper())
    name.setObjectName("metricLabel")
    output = QLabel(value)
    output.setObjectName("metricValue")
    output.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(name)
    layout.addStretch()
    layout.addWidget(output)
    return row, output
