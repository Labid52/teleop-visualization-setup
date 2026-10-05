"""Deterministic synthetic GPS motion for diagnostics and tests."""

from __future__ import annotations

import math
import threading
import time

from visualization.common.models import GPSFix, ProviderStatus, SCHEMA_VERSION
from visualization.common.timestamps import now
from visualization.onboard.providers.base_gps import GPSProvider
from visualization.onboard.providers.errors import ProviderFailure


class MockGPSProvider(GPSProvider):
    def __init__(self, source_id: str = "mock_gps", origin_latitude: float = 35.0, origin_longitude: float = -97.0, target_hz: float = 10.0, speed_mps: float = 4.0, heading_deg: float = 45.0, fail_after_updates: int | None = None) -> None:
        if target_hz <= 0:
            raise ValueError("target_hz must be positive")
        self.source_id = source_id
        self.origin_latitude = origin_latitude
        self.origin_longitude = origin_longitude
        self.target_hz = target_hz
        self.speed_mps = speed_mps
        self.heading_deg = heading_deg
        self.fail_after_updates = fail_after_updates
        self._sequence = 0
        self._next_update_at = 0.0
        self._state = ProviderStatus("stopped")
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._sequence = 0
            self._next_update_at = time.monotonic()
            self._state = ProviderStatus("running")

    def get_latest(self) -> GPSFix:
        with self._lock:
            if self._state.state != "running":
                raise ProviderFailure(self._state.detail or "mock GPS is not running")
            sequence = self._sequence
            if self.fail_after_updates is not None and sequence >= self.fail_after_updates:
                self._state = ProviderStatus("failed", "simulated GPS failure")
                raise ProviderFailure(self._state.detail)
            deadline = self._next_update_at
        delay = deadline - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elapsed_s = sequence / self.target_hz
        distance_m = self.speed_mps * elapsed_s
        heading_rad = math.radians(self.heading_deg)
        north_m = math.cos(heading_rad) * distance_m
        east_m = math.sin(heading_rad) * distance_m
        latitude = self.origin_latitude + north_m / 111_111.0
        lon_scale = 111_111.0 * max(0.1, math.cos(math.radians(self.origin_latitude)))
        longitude = self.origin_longitude + east_m / lon_scale
        stamp = now()
        fix = GPSFix(SCHEMA_VERSION, self.source_id, sequence, stamp.utc, stamp.monotonic_s, latitude, longitude, 300.0, self.speed_mps, self.heading_deg, True, 10, 1.5)
        with self._lock:
            self._sequence += 1
            period = 1.0 / self.target_hz
            self._next_update_at = max(self._next_update_at + period, time.monotonic())
        return fix

    def stop(self) -> None:
        with self._lock:
            self._state = ProviderStatus("stopped")

    def status(self) -> ProviderStatus:
        with self._lock:
            return self._state
