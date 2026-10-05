"""Safe, credential-free operator-console preferences."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from visualization.gui.models.ui_state import CameraId


@dataclass(frozen=True)
class WindowConfig:
    fullscreen: bool = False
    width: int = 1600
    height: int = 900
    minimum_width: int = 1180
    minimum_height: int = 720


@dataclass(frozen=True)
class CameraUiConfig:
    enabled: bool = True
    target_fps: float = 18.0


@dataclass(frozen=True)
class GPSUiConfig:
    enabled: bool = True
    target_hz: float = 10.0


@dataclass(frozen=True)
class UiConfig:
    show_network_panel: bool = True
    show_event_log: bool = True
    maximum_events: int = 80


DEFAULT_ACTIONS = {
    "L2": "NEAR_LEFT",
    "L3": "FAR_LEFT",
    "R2": "NEAR_RIGHT",
    "R3": "FAR_RIGHT",
    "TRIANGLE": "ABORT",
}


@dataclass(frozen=True)
class GuiConfig:
    window: WindowConfig = field(default_factory=WindowConfig)
    cameras: dict[CameraId, CameraUiConfig] = field(default_factory=lambda: {
        CameraId.FRONT: CameraUiConfig(target_fps=20.0),
        CameraId.LEFT: CameraUiConfig(target_fps=18.0),
        CameraId.RIGHT: CameraUiConfig(target_fps=18.0),
        CameraId.CABIN: CameraUiConfig(target_fps=16.0),
    })
    gps: GPSUiConfig = field(default_factory=GPSUiConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    provisional_button_actions: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_ACTIONS))


def _construct(cls: type, values: dict[str, Any]) -> Any:
    unknown = set(values) - set(cls.__dataclass_fields__)
    if unknown:
        raise ValueError(f"unknown {cls.__name__} fields: {sorted(unknown)}")
    return cls(**values)


def load_gui_config(path: str | Path) -> GuiConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("GUI configuration root must be a mapping")
    allowed = {"window", "cameras", "gps", "ui", "provisional_button_actions"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown GUI configuration fields: {sorted(unknown)}")
    camera_raw = raw.get("cameras", {})
    unknown_cameras = set(camera_raw) - {camera.value for camera in CameraId}
    if unknown_cameras:
        raise ValueError(f"unknown camera IDs: {sorted(unknown_cameras)}")
    defaults = GuiConfig()
    cameras = {
        camera_id: _construct(CameraUiConfig, camera_raw.get(camera_id.value, {"enabled": defaults.cameras[camera_id].enabled, "target_fps": defaults.cameras[camera_id].target_fps}))
        for camera_id in CameraId
    }
    actions = dict(DEFAULT_ACTIONS)
    actions.update(raw.get("provisional_button_actions", {}))
    if set(actions) != set(DEFAULT_ACTIONS):
        raise ValueError("provisional mapping must contain exactly L2, L3, R2, R3, and TRIANGLE")
    return GuiConfig(
        window=_construct(WindowConfig, raw.get("window", {})),
        cameras=cameras,
        gps=_construct(GPSUiConfig, raw.get("gps", {})),
        ui=_construct(UiConfig, raw.get("ui", {})),
        provisional_button_actions=actions,
    )
