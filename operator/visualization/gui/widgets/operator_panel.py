"""Read-only steering, pedal, and source-mode presentation."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel

from visualization.gui.models.ui_state import OperatorState
from visualization.gui.widgets.common import PanelFrame, StateBadge
from visualization.gui.widgets.pedal_widget import PedalWidget
from visualization.gui.widgets.steering_widget import SteeringWidget


class OperatorPanel(PanelFrame):
    def __init__(self, parent=None) -> None:
        super().__init__("OPERATOR COMMANDS", "DISPLAY-ONLY MIRROR", parent)
        self.badge = StateBadge("MOCK")
        self.outer.itemAt(0).layout().addWidget(self.badge)
        self.steering = SteeringWidget()
        self.outer.addWidget(self.steering)
        pedals = QHBoxLayout()
        self.throttle = PedalWidget("Throttle", "throttle")
        self.brake = PedalWidget("Brake", "brake")
        pedals.addWidget(self.throttle)
        pedals.addWidget(self.brake)
        self.outer.addLayout(pedals)
        self.sequence = QLabel("SOURCE SEQ --")
        self.sequence.setObjectName("cameraMetric")
        self.outer.addWidget(self.sequence)

    def update_operator(self, state: OperatorState) -> None:
        self.badge.set_state(state.state.value)
        self.steering.set_value(state.steering)
        self.throttle.set_value(state.throttle)
        self.brake.set_value(state.brake)
        self.sequence.setText(f"SOURCE SEQ {state.sequence}")
