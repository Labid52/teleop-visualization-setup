"""Onboard visualization agent; it has no dependency on vehicle control."""

from __future__ import annotations

import argparse
import signal
import threading
import time

from visualization.onboard.config import VisualizationConfig, load_config
from visualization.onboard.pipeline.telemetry_pipeline import TelemetryPipeline
from visualization.onboard.pipeline.video_pipeline import VideoPipeline
from visualization.onboard.providers.base_camera import CameraProvider
from visualization.onboard.providers.base_gps import GPSProvider
from visualization.onboard.providers.mock_camera import MockCameraProvider
from visualization.onboard.providers.mock_gps import MockGPSProvider
from visualization.onboard.providers.system_health import SystemHealthProvider
from visualization.onboard.providers.usb_camera import UsbCameraProvider
from visualization.onboard.transport.local_telemetry_server import LocalTelemetryServer
from visualization.onboard.transport.local_video_server import LocalVideoServer


def build_camera(config: VisualizationConfig) -> CameraProvider:
    camera = config.camera
    if camera.provider == "mock":
        return MockCameraProvider(camera.source_id, camera.width, camera.height, camera.target_fps)
    if camera.provider == "usb":
        return UsbCameraProvider(camera.device, camera.width, camera.height, camera.target_fps, camera.source_id)
    raise ValueError(f"unsupported camera provider: {camera.provider}")


def build_gps(config: VisualizationConfig) -> GPSProvider:
    gps = config.gps
    if gps.provider == "mock":
        return MockGPSProvider(gps.source_id, gps.origin_latitude, gps.origin_longitude, gps.target_hz, gps.speed_mps, gps.heading_deg)
    raise ValueError(f"unsupported GPS provider: {gps.provider}")


class VisualizationAgent:
    def __init__(self, config: VisualizationConfig, camera: CameraProvider | None = None, gps: GPSProvider | None = None) -> None:
        self.config = config
        self.video = VideoPipeline(camera or build_camera(config), config.camera.queue_size, config.camera.jpeg_quality)
        self.telemetry = TelemetryPipeline(gps or build_gps(config), SystemHealthProvider(), self.video, config.source_id, config.telemetry.target_hz, config.telemetry.queue_size)
        self.telemetry_server = LocalTelemetryServer(self.telemetry.queue, config.telemetry.local_host, config.telemetry.local_port)
        self.video_server = LocalVideoServer(self.video.queue, config.video.local_host, config.video.local_port)
        self.started = False

    def start(self) -> None:
        if self.started:
            return
        try:
            self.video.start()
            self.telemetry.start()
            self.telemetry_server.start()
            if self.config.video.diagnostic_mode:
                self.video_server.start()
            self.started = True
        except Exception:
            self.telemetry_server.stop()
            self.video_server.stop()
            self.telemetry.stop()
            self.video.stop()
            raise

    def stop(self) -> None:
        if not self.started:
            return
        self.telemetry_server.stop()
        if self.config.video.diagnostic_mode:
            self.video_server.stop()
        self.telemetry.stop()
        self.video.stop()
        self.started = False

    def all_threads_stopped(self) -> bool:
        return not any((self.video.is_alive(), self.telemetry.is_alive(), self.telemetry_server.is_alive(), self.video_server.is_alive()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated onboard visualization agent")
    parser.add_argument("--config", default="visualization/config/visualization.example.yaml")
    parser.add_argument("--duration", type=float, default=0.0, help="stop after seconds; zero runs until Ctrl+C")
    args = parser.parse_args()
    agent = VisualizationAgent(load_config(args.config))
    stopping = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    agent.start()
    print(f"Telemetry: 127.0.0.1:{agent.telemetry_server.port}; video: 127.0.0.1:{agent.video_server.port}")
    started = time.monotonic()
    try:
        while not stopping.wait(0.2):
            if args.duration > 0 and time.monotonic() - started >= args.duration:
                break
    finally:
        agent.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
