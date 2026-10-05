"""Low-rate telemetry acquisition isolated from the video pipeline."""

from __future__ import annotations

import threading
import time

from visualization.common.bounded_queue import DropOldestQueue, QueueClosed
from visualization.common.models import CameraTelemetry, GPSFix, SCHEMA_VERSION, TelemetryMessage
from visualization.common.timestamps import now
from visualization.onboard.pipeline.video_pipeline import VideoPipeline
from visualization.onboard.providers.base_gps import GPSProvider
from visualization.onboard.providers.base_health import HealthContext, HealthProvider
from visualization.onboard.providers.errors import ProviderFailure


class TelemetryPipeline:
    def __init__(self, gps: GPSProvider, health: HealthProvider, video: VideoPipeline, source_id: str = "onboard_pc", target_hz: float = 10.0, queue_size: int = 20) -> None:
        if target_hz <= 0:
            raise ValueError("target_hz must be positive")
        self.gps = gps
        self.health = health
        self.video = video
        self.source_id = source_id
        self.target_hz = target_hz
        self.queue: DropOldestQueue[TelemetryMessage] = DropOldestQueue(queue_size)
        self.latest_gps: GPSFix | None = None
        self.error: str | None = None
        self._started_at = 0.0
        self._stopped_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.gps.start()
        self._started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="viz-telemetry-acquisition", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        sequence = 0
        deadline = time.monotonic()
        try:
            while not self._stop.is_set():
                try:
                    self.latest_gps = self.gps.get_latest()
                except ProviderFailure as exc:
                    self.error = str(exc)
                    self.latest_gps = None

                stamp = now()
                video_stats = self.video.queue.stats()
                own_stats = self.queue.stats()
                camera_status = self.video.provider_status()
                gps_status = self.gps.status()
                metadata = self.video.latest_metadata
                camera = CameraTelemetry(
                    source_id=metadata.source_id if metadata else "unavailable",
                    provider_state=camera_status.state,
                    latest_frame_sequence=metadata.frame_sequence if metadata else None,
                    latest_capture_time_utc=metadata.capture_time_utc if metadata else None,
                    latest_capture_time_monotonic_s=metadata.capture_time_monotonic_s if metadata else None,
                    width=metadata.width if metadata else None,
                    height=metadata.height if metadata else None,
                    fps_target=metadata.fps_target if metadata else 0.0,
                    frames_produced=video_stats.produced,
                    frames_dropped_locally=video_stats.dropped_oldest,
                    queue_depth=video_stats.depth,
                )
                context = HealthContext(
                    camera_provider_state=camera_status.state,
                    gps_provider_state=gps_status.state,
                    telemetry_rate_hz=self.produced_rate_hz(),
                    video_frame_rate_hz=self.video.produced_rate_hz(),
                    dropped_local_frames=video_stats.dropped_oldest,
                    video_queue_depth=video_stats.depth,
                    telemetry_queue_depth=own_stats.depth,
                )
                message = TelemetryMessage(
                    schema_version=SCHEMA_VERSION,
                    message_type="vehicle_visualization",
                    source_id=self.source_id,
                    sequence=sequence,
                    timestamp_utc=stamp.utc,
                    timestamp_monotonic_s=stamp.monotonic_s,
                    gps_status=gps_status.state,
                    gps=self.latest_gps,
                    system=self.health.get_latest(context),
                    camera=camera,
                )
                self.queue.put(message)
                sequence += 1
                deadline += 1.0 / self.target_hz
                self._stop.wait(max(0.0, deadline - time.monotonic()))
                if deadline < time.monotonic() - 1.0:
                    deadline = time.monotonic()
        except QueueClosed:
            pass
        except Exception as exc:  # telemetry failure remains local to this thread
            self.error = f"unexpected telemetry failure: {exc}"
        finally:
            self._stopped_at = time.monotonic()
            self.gps.stop()

    def stop(self) -> None:
        self._stop.set()
        self.queue.close()
        if self._thread:
            self._thread.join(timeout=3.0)
        self.gps.stop()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def produced_rate_hz(self) -> float:
        if not self._started_at:
            return 0.0
        end = self._stopped_at or time.monotonic()
        return self.queue.stats().produced / max(1e-9, end - self._started_at)
