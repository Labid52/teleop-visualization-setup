"""Mock GPS, health, and honest placeholder network metrics."""

from __future__ import annotations

from dataclasses import replace
import math
import time

from visualization.gui.models.ui_state import DisplayState, GPSState, HealthState, NetworkState, TelemetryState
from visualization.gui.sources.base import TelemetrySource
from visualization.onboard.providers.base_health import HealthContext
from visualization.onboard.providers.mock_gps import MockGPSProvider
from visualization.onboard.providers.system_health import SystemHealthProvider


class MockTelemetrySource(TelemetrySource):
    def __init__(self, target_hz: float = 10.0) -> None:
        self.target_hz = target_hz
        self._gps = MockGPSProvider(source_id="gui_mock_gps", target_hz=target_hz, speed_mps=4.0, heading_deg=35.0)
        self._health = SystemHealthProvider()
        self._started_at = 0.0

    def start(self) -> None:
        self._started_at = time.monotonic()
        self._gps.start()

    def get_latest(self) -> TelemetryState:
        fix = self._gps.get_latest()
        elapsed = time.monotonic() - self._started_at
        heading = (35.0 + elapsed * 7.0) % 360.0
        speed = 4.5 + 2.0 * math.sin(elapsed / 4.0)
        fix = replace(fix, heading_deg=heading, speed_mps=max(0.0, speed))
        gps = GPSState(fix.sequence, fix.timestamp_utc, fix.timestamp_monotonic_s, fix.latitude, fix.longitude, fix.speed_mps, fix.heading_deg, fix.fix_valid, fix.satellites, fix.horizontal_accuracy_m, DisplayState.MOCK)
        health_record = self._health.get_latest(HealthContext("running", "running", self.target_hz, 18.0, 0, 0, 0))
        health = HealthState(health_record.cpu_percent, health_record.memory_percent, health_record.process_rss_bytes, elapsed, DisplayState.MOCK, self.target_hz, 18.0, self.target_hz, DisplayState.MOCK)
        network = NetworkState(18.0, self.target_hz, 0.0, max(0.0, time.monotonic() - fix.timestamp_monotonic_s), 0, "640×360", None, None, None, DisplayState.MOCK)
        return TelemetryState(gps, health, network)

    def stop(self) -> None:
        self._gps.stop()
