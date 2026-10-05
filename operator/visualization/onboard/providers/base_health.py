"""Host-health provider contract and pipeline context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from visualization.common.models import SystemHealth


@dataclass(frozen=True)
class HealthContext:
    camera_provider_state: str
    gps_provider_state: str
    telemetry_rate_hz: float
    video_frame_rate_hz: float
    dropped_local_frames: int
    video_queue_depth: int
    telemetry_queue_depth: int


class HealthProvider(ABC):
    @abstractmethod
    def get_latest(self, context: HealthContext) -> SystemHealth: ...
