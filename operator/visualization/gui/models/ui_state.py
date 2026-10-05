"""Transport-independent state consumed by operator-console widgets."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CameraId(str, Enum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    CABIN = "cabin"


class DisplayState(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    MOCK = "MOCK"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    WAITING = "WAITING"
    NO_DATA = "NO DATA"


@dataclass(frozen=True)
class VideoFrameState:
    camera_id: CameraId
    image_bgr: Any
    sequence: int
    capture_time_utc: str
    capture_time_monotonic_s: float
    width: int
    height: int
    fps_target: float
    state: DisplayState = DisplayState.MOCK
    bitrate_kbps: float | None = None
    recording: bool = False
    timestamp_origin: str = "capture"


@dataclass(frozen=True)
class GPSState:
    sequence: int
    timestamp_utc: str
    timestamp_monotonic_s: float
    latitude: float | None
    longitude: float | None
    speed_mps: float | None
    heading_deg: float | None
    fix_valid: bool
    satellites: int | None
    horizontal_accuracy_m: float | None
    state: DisplayState = DisplayState.MOCK
    heading_source: str = "UNAVAILABLE"
    published: bool = True


@dataclass(frozen=True)
class HealthState:
    cpu_percent: float | None
    memory_percent: float | None
    process_rss_bytes: int | None
    uptime_s: float | None
    video_pipeline_state: DisplayState
    telemetry_rate_hz: float | None
    camera_fps: float | None
    gps_rate_hz: float | None
    state: DisplayState = DisplayState.MOCK
    temperature_c: float | None = None


@dataclass(frozen=True)
class NetworkState:
    video_fps: float | None
    telemetry_hz: float
    video_freshness_s: float | None
    gps_freshness_s: float | None
    dropped_frames: int | None
    resolution: str
    bitrate_kbps: float | None = None
    rtt_ms: float | None = None
    packet_loss_percent: float | None = None
    state: DisplayState = DisplayState.MOCK


@dataclass(frozen=True)
class CameraHealthState:
    healthy: bool | None
    fps: float | None
    frame_age_s: float | None
    stream_path: str


@dataclass(frozen=True)
class TelemetryState:
    gps: GPSState
    health: HealthState
    network: NetworkState
    sequence: int | None = None
    timestamp_utc: str = ""
    received_monotonic_s: float = 0.0
    state: DisplayState = DisplayState.MOCK
    cameras: dict[CameraId, CameraHealthState] = field(default_factory=dict)


@dataclass(frozen=True)
class OperatorState:
    sequence: int
    timestamp_monotonic_s: float
    steering: float
    throttle: float
    brake: float
    pressed_buttons: frozenset[str]
    state: DisplayState = DisplayState.MOCK
