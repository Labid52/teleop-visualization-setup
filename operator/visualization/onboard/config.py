"""Safe configuration loading for the visualization-only agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CameraConfig:
    provider: str = "mock"
    device: int | str = 0
    source_id: str = "onboard_camera"
    width: int = 640
    height: int = 360
    target_fps: float = 20.0
    queue_size: int = 3
    jpeg_quality: int = 80


@dataclass(frozen=True)
class GPSConfig:
    provider: str = "mock"
    source_id: str = "onboard_gps"
    target_hz: float = 10.0
    origin_latitude: float = 35.0
    origin_longitude: float = -97.0
    speed_mps: float = 4.0
    heading_deg: float = 45.0


@dataclass(frozen=True)
class TelemetryConfig:
    target_hz: float = 10.0
    queue_size: int = 20
    local_host: str = "127.0.0.1"
    local_port: int = 8765


@dataclass(frozen=True)
class VideoConfig:
    diagnostic_mode: bool = True
    local_host: str = "127.0.0.1"
    local_port: int = 8766


@dataclass(frozen=True)
class VisualizationConfig:
    source_id: str = "onboard_pc"
    camera: CameraConfig = field(default_factory=CameraConfig)
    gps: GPSConfig = field(default_factory=GPSConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    video: VideoConfig = field(default_factory=VideoConfig)


def _known_fields(values: dict[str, Any], cls: type) -> dict[str, Any]:
    names = cls.__dataclass_fields__.keys()
    unknown = set(values) - set(names)
    if unknown:
        raise ValueError(f"unknown {cls.__name__} fields: {sorted(unknown)}")
    return values


def load_config(path: str | Path) -> VisualizationConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")
    allowed = {"source_id", "camera", "gps", "telemetry", "video"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown configuration fields: {sorted(unknown)}")
    return VisualizationConfig(
        source_id=raw.get("source_id", "onboard_pc"),
        camera=CameraConfig(**_known_fields(raw.get("camera", {}), CameraConfig)),
        gps=GPSConfig(**_known_fields(raw.get("gps", {}), GPSConfig)),
        telemetry=TelemetryConfig(**_known_fields(raw.get("telemetry", {}), TelemetryConfig)),
        video=VideoConfig(**_known_fields(raw.get("video", {}), VideoConfig)),
    )
