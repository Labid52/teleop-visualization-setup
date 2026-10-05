"""Deterministic display-only operator input animation."""

from __future__ import annotations

import math
import time

from visualization.gui.models.ui_state import DisplayState, OperatorState
from visualization.gui.sources.base import OperatorStateSource


class MockOperatorStateSource(OperatorStateSource):
    BUTTONS = ("L2", "L3", "R2", "R3", "TRIANGLE")

    def __init__(self, target_hz: float = 20.0) -> None:
        self.target_hz = target_hz
        self._sequence = 0
        self._started_at = 0.0
        self._next_at = 0.0

    def start(self) -> None:
        self._sequence = 0
        self._started_at = self._next_at = time.monotonic()

    def get_latest(self) -> OperatorState:
        delay = self._next_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        current = time.monotonic()
        elapsed = current - self._started_at
        steering = 0.78 * math.sin(elapsed * 0.72)
        throttle = 0.5 + 0.42 * math.sin(elapsed * 0.39)
        brake = max(0.0, 0.7 * math.sin(elapsed * 0.31 - 1.4))
        phase = elapsed % 15.0
        button_index = int(phase // 3.0)
        pressed = frozenset({self.BUTTONS[button_index]}) if phase % 3.0 < 0.35 else frozenset()
        state = OperatorState(self._sequence, current, steering, min(1.0, max(0.0, throttle)), min(1.0, brake), pressed, DisplayState.MOCK)
        self._sequence += 1
        self._next_at = max(self._next_at + 1.0 / self.target_hz, time.monotonic())
        return state

    def stop(self) -> None:
        pass
