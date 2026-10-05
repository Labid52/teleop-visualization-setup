"""Lightweight onboard-computer diagnostics; never a control safety input."""

from __future__ import annotations

import os
import time

import psutil

from visualization.common.models import SystemHealth
from visualization.onboard.providers.base_health import HealthContext, HealthProvider


class SystemHealthProvider(HealthProvider):
    def __init__(self) -> None:
        self._process = psutil.Process(os.getpid())

    def get_latest(self, context: HealthContext) -> SystemHealth:
        return SystemHealth(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=psutil.virtual_memory().percent,
            process_rss_bytes=self._process.memory_info().rss,
            system_uptime_s=max(0.0, time.time() - psutil.boot_time()),
            camera_provider_state=context.camera_provider_state,
            gps_provider_state=context.gps_provider_state,
            telemetry_rate_hz=context.telemetry_rate_hz,
            video_frame_rate_hz=context.video_frame_rate_hz,
            dropped_local_frames=context.dropped_local_frames,
            video_queue_depth=context.video_queue_depth,
            telemetry_queue_depth=context.telemetry_queue_depth,
        )
