"""Typed visualization records and JSON-safe serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProviderStatus:
    state: str
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.state == "running"


@dataclass(frozen=True)
class FrameMetadata:
    schema_version: int
    source_id: str
    frame_sequence: int
    capture_time_utc: str
    capture_time_monotonic_s: float
    width: int
    height: int
    fps_target: float
    provider_status: str


@dataclass(frozen=True)
class EncodedFrame:
    metadata: FrameMetadata
    jpeg_bytes: bytes


@dataclass(frozen=True)
class GPSFix:
    schema_version: int
    source_id: str
    sequence: int
    timestamp_utc: str
    timestamp_monotonic_s: float
    latitude: float
    longitude: float
    altitude_m: float | None
    speed_mps: float
    heading_deg: float
    fix_valid: bool
    satellites: int | None
    horizontal_accuracy_m: float | None


@dataclass(frozen=True)
class SystemHealth:
    cpu_percent: float
    memory_percent: float
    process_rss_bytes: int
    system_uptime_s: float
    camera_provider_state: str
    gps_provider_state: str
    telemetry_rate_hz: float
    video_frame_rate_hz: float
    dropped_local_frames: int
    video_queue_depth: int
    telemetry_queue_depth: int


@dataclass(frozen=True)
class CameraTelemetry:
    source_id: str
    provider_state: str
    latest_frame_sequence: int | None
    latest_capture_time_utc: str | None
    latest_capture_time_monotonic_s: float | None
    width: int | None
    height: int | None
    fps_target: float
    frames_produced: int
    frames_dropped_locally: int
    queue_depth: int


@dataclass(frozen=True)
class TelemetryMessage:
    schema_version: int
    message_type: str
    source_id: str
    sequence: int
    timestamp_utc: str
    timestamp_monotonic_s: float
    gps_status: str
    gps: GPSFix | None
    system: SystemHealth
    camera: CameraTelemetry

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), allow_nan=False)
