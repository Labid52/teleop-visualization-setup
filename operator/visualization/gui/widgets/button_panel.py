"""Physical-button indicators with centralized provisional action labels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from visualization.gui.models.ui_state import OperatorState
from visualization.gui.widgets.common import PanelFrame


class ButtonCard(QFrame):
    def __init__(self, physical_name: str, provisional_action: str) -> None:
        super().__init__()
        self.setObjectName("buttonCard")
        self.setProperty("pressed", False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(2)
        self.name = QLabel(physical_name)
        self.name.setObjectName("buttonName")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.action = QLabel(f"PROVISIONAL · {provisional_action}")
        self.action.setObjectName("buttonAction")
        self.action.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name)
        layout.addWidget(self.action)

    def set_pressed(self, pressed: bool) -> None:
        self.setProperty("pressed", pressed)
        self.style().unpolish(self)
        self.style().polish(self)


class ButtonPanel(PanelFrame):
    def __init__(self, mapping: dict[str, str], parent=None) -> None:
        super().__init__("PHYSICAL BUTTONS", "PROVISIONAL ASSIGNMENTS", parent)
        self.mapping = dict(mapping)
        self.cards: dict[str, ButtonCard] = {}
        grid = QGridLayout()
        positions = {"L2": (0, 0), "L3": (0, 1), "R2": (0, 2), "R3": (0, 3), "TRIANGLE": (1, 0)}
        for name, position in positions.items():
            card = ButtonCard(name.title() if name == "TRIANGLE" else name, self.mapping.get(name, "UNASSIGNED"))
            self.cards[name] = card
            if name == "TRIANGLE":
                grid.addWidget(card, 1, 0, 1, 4)
            else:
                grid.addWidget(card, *position)
        self.outer.addLayout(grid)
        self.last_pressed: frozenset[str] = frozenset()

    def update_operator(self, state: OperatorState) -> list[str]:
        new_presses = state.pressed_buttons - self.last_pressed
        for name, card in self.cards.items():
            card.set_pressed(name in state.pressed_buttons)
        self.last_pressed = state.pressed_buttons
        return sorted(new_presses)
