"""Pytest helpers for isolated visualization tests."""

from __future__ import annotations

from dataclasses import replace
import time

from visualization.onboard.config import VisualizationConfig


def ephemeral_config(**changes: object) -> VisualizationConfig:
    config = VisualizationConfig()
    config = replace(
        config,
        camera=replace(config.camera, width=320, height=180, target_fps=30.0, queue_size=2),
        gps=replace(config.gps, target_hz=20.0),
        telemetry=replace(config.telemetry, target_hz=20.0, local_port=0),
        video=replace(config.video, local_port=0),
    )
    return replace(config, **changes)


def wait_until(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False
