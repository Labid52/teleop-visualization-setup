"""Command-line entry point for the four-camera operator console."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

from visualization.gui.config import load_gui_config
from visualization.gui.main_window import OperatorConsole
from visualization.gui.minimal_window import MinimalOperatorConsole
from visualization.gui.sources.mock_operator_source import MockOperatorStateSource
from visualization.gui.sources.mock_telemetry_source import MockTelemetrySource
from visualization.gui.sources.mock_video_source import MockVideoSource
from visualization.gui.sources.workers import GuiSourceController
from visualization.gui.sources.wan_config import load_wan_credentials
from visualization.gui.sources.wan_video_source import WanVideoSource
from visualization.gui.sources.wan_telemetry_source import WanTelemetrySource
from visualization.gui.sources.no_operator_source import NoOperatorStateSource
from visualization.gui.models.ui_state import CameraId
from visualization.gui.sources.console_demo import ConsoleDemoVideo, ConsoleDemoTelemetry
from visualization.gui.two_camera_window import TwoCameraOperatorConsole
from visualization.gui.sources.two_camera_demo import TwoCameraDemoVideo


def build_demo_console(config_path: str) -> OperatorConsole:
    config = load_gui_config(config_path)
    rates = {camera_id: camera.target_fps for camera_id, camera in config.cameras.items()}
    enabled = {camera_id for camera_id, camera in config.cameras.items() if camera.enabled}
    controller = GuiSourceController(MockVideoSource(fps=rates, enabled=enabled), MockTelemetrySource(config.gps.target_hz), MockOperatorStateSource())
    return OperatorConsole(config, controller)


def build_wan_console(config_path: str, secrets_file: str, decoder: str = "ffmpeg") -> OperatorConsole:
    config = load_gui_config(config_path)
    credentials = load_wan_credentials(secrets_file)
    enabled = {camera_id for camera_id, camera in config.cameras.items() if camera.enabled}
    controller = GuiSourceController(WanVideoSource(credentials, enabled, executable=decoder), WanTelemetrySource(credentials), NoOperatorStateSource())
    return OperatorConsole(config, controller)


def build_minimal_wan_console(secrets_file: str, decoder: str = "ffmpeg") -> MinimalOperatorConsole:
    credentials = load_wan_credentials(secrets_file)
    controller = GuiSourceController(
        WanVideoSource(credentials, enabled={CameraId.CABIN}, executable=decoder),
        WanTelemetrySource(credentials), NoOperatorStateSource())
    return MinimalOperatorConsole(controller)


def build_minimal_demo_console(config_path: str) -> MinimalOperatorConsole:
    config = load_gui_config(config_path)
    controller = GuiSourceController(
        ConsoleDemoVideo(), ConsoleDemoTelemetry(config.gps.target_hz), NoOperatorStateSource())
    return MinimalOperatorConsole(controller)


def build_two_camera_wan_console(secrets_file: str, decoder: str = "ffmpeg", show_button: bool = False) -> TwoCameraOperatorConsole:
    credentials = load_wan_credentials(secrets_file)
    controller = GuiSourceController(
        WanVideoSource(credentials, enabled={CameraId.FRONT, CameraId.CABIN}, executable=decoder),
        WanTelemetrySource(credentials), NoOperatorStateSource())
    return TwoCameraOperatorConsole(controller, show_button=show_button)


def build_two_camera_demo_console(config_path: str, show_button: bool = False) -> TwoCameraOperatorConsole:
    config = load_gui_config(config_path)
    controller = GuiSourceController(
        TwoCameraDemoVideo(), ConsoleDemoTelemetry(config.gps.target_hz), NoOperatorStateSource())
    return TwoCameraOperatorConsole(controller, show_button=show_button)


def main() -> int:
    parser = argparse.ArgumentParser(description="MILA four-camera operator console shell")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="run all sources in deterministic mock mode")
    mode.add_argument("--wan", action="store_true", help="read full real WAN visualization; controls remain separate")
    mode.add_argument("--minimal-wan", action="store_true", help="read only cabin video and essential GNSS")
    mode.add_argument("--minimal-demo", action="store_true", help="run the compact cabin/GNSS view with mock sources")
    mode.add_argument("--two-camera-wan", action="store_true", help="read front and cabin video with GNSS")
    mode.add_argument("--two-camera-demo", action="store_true", help="demonstrate front and cabin video with GNSS")
    parser.add_argument("--secrets-file", default="~/.config/teleop_visualization/oci_visualization.env")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="optional installed SRT-capable decoder path")
    parser.add_argument("--config", default="visualization/config/gui.example.yaml")
    parser.add_argument("--duration", type=float, default=0.0, help="automatically close after seconds")
    parser.add_argument("--metrics-output", help="write final performance metrics as JSON")
    parser.add_argument("--screenshot-after", type=float, default=0.0, help="capture a screenshot after seconds")
    parser.add_argument("--screenshot-output", help="screenshot path; defaults to ignored output directory")
    parser.add_argument("--maximized", action="store_true", help="open maximized on the current display")
    parser.add_argument("--button", action="store_true", help="show the G29 button-region guide beside ground speed")
    args = parser.parse_args()

    if args.button and not (args.two_camera_wan or args.two_camera_demo):
        parser.error("--button requires --two-camera-wan or --two-camera-demo")

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("MILA Remote Vehicle Operator Console")
    try:
        if args.two_camera_wan:
            window = build_two_camera_wan_console(args.secrets_file, args.ffmpeg, args.button)
        elif args.two_camera_demo:
            window = build_two_camera_demo_console(args.config, args.button)
        elif args.minimal_wan:
            window = build_minimal_wan_console(args.secrets_file, args.ffmpeg)
        elif args.minimal_demo:
            window = build_minimal_demo_console(args.config)
        else:
            window = build_wan_console(args.config, args.secrets_file, args.ffmpeg) if args.wan else build_demo_console(args.config)
    except (OSError, ValueError):
        parser.error("Unable to initialize sources; check private reader configuration and installed decoder")
    window_config = getattr(window, "config", None)
    if window_config is not None and window_config.window.fullscreen:
        window.showFullScreen()
    elif args.maximized:
        window.showMaximized()
    else:
        window.show()
    window.start_sources()
    if args.screenshot_after > 0:
        QTimer.singleShot(round(args.screenshot_after * 1000), lambda: window.capture_screenshot(args.screenshot_output))
    if args.duration > 0:
        QTimer.singleShot(round(args.duration * 1000), window.close)
    exit_code = app.exec()
    metrics = window.metrics() if hasattr(window, "metrics") else {}
    metrics["clean_shutdown"] = window.sources.threads_running() == 0
    if args.metrics_output:
        path = Path(args.metrics_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
