"""Responsive four-camera operator-console window."""

from __future__ import annotations

from datetime import datetime, timezone
from collections import deque
from dataclasses import replace
from pathlib import Path
import time

import psutil

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QGridLayout, QLabel, QMainWindow, QScrollArea, QSplitter, QVBoxLayout, QWidget

from visualization.gui.config import GuiConfig
from visualization.gui.models.ui_state import CameraId, DisplayState, OperatorState, TelemetryState, VideoFrameState
from visualization.gui.sources.workers import GuiSourceController
from visualization.gui.theme import STYLESHEET
from visualization.gui.widgets.bottom_bar import BottomBar
from visualization.gui.widgets.button_panel import ButtonPanel
from visualization.gui.widgets.camera_tile import CameraTile
from visualization.gui.widgets.event_log import EventLogPanel
from visualization.gui.widgets.gps_panel import GPSPanel
from visualization.gui.widgets.network_status import NetworkStatusPanel
from visualization.gui.widgets.operator_panel import OperatorPanel
from visualization.gui.widgets.system_status import SystemStatusPanel
from visualization.gui.widgets.top_bar import TopBar


class OperatorConsole(QMainWindow):
    CAMERA_POSITIONS = {
        CameraId.FRONT: (0, 0, 1, 2),
        CameraId.LEFT: (1, 0, 1, 1),
        CameraId.RIGHT: (1, 1, 1, 1),
        CameraId.CABIN: (2, 0, 1, 2),
    }

    def __init__(self, config: GuiConfig, sources: GuiSourceController) -> None:
        super().__init__()
        self.config = config
        self.sources = sources
        self.mode = getattr(sources.video, "mode", "MOCK")
        self.last_telemetry = None
        self.started_at = time.monotonic()
        self.maximized_camera: CameraId | None = None
        self.last_health = None
        self.rss_samples = deque(maxlen=1200)
        self.rss_timed_samples = deque(maxlen=1200)
        self.cpu_samples = deque(maxlen=1200)
        self.process_cpu_samples = deque(maxlen=1200)
        self.child_rss_samples = deque(maxlen=1200)
        self.child_cpu_samples = deque(maxlen=1200)
        self._child_processes = {}
        self._process = psutil.Process()
        self._process.cpu_percent(interval=None)
        self.telemetry_updates = 0
        self._last_buttons: frozenset[str] = frozenset()
        self._last_heartbeat = time.monotonic()
        self.maximum_gui_timer_delay_s = 0.0
        self.gui_heartbeat_count = 0
        self.setWindowTitle(f"MILA Remote Vehicle Operator Console · {self.mode} Visualization")
        self.setMinimumSize(config.window.minimum_width, config.window.minimum_height)
        self.resize(config.window.width, config.window.height)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        central.setObjectName("central")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.top_bar = TopBar()
        self.top_bar.screenshot_requested.connect(self.capture_screenshot)
        root.addWidget(self.top_bar)
        self.telemetry_summary = QLabel("TELEMETRY · CONNECTING   |   GNSS · NO DATA")
        self.telemetry_summary.setContentsMargins(18, 7, 18, 7)
        self.telemetry_summary.setObjectName("metricLabel")
        self.telemetry_summary.setStyleSheet("font-size: 12px; color: #a9c1d5;")
        self.telemetry_summary.setVisible(self.mode == "WAN")
        root.addWidget(self.telemetry_summary)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.camera_area = QWidget()
        self.camera_grid = QGridLayout(self.camera_area)
        self.camera_grid.setContentsMargins(10, 10, 5, 10)
        self.camera_grid.setSpacing(8)
        self.camera_grid.setRowStretch(0, 5)
        self.camera_grid.setRowStretch(1, 3)
        self.camera_grid.setRowStretch(2, 3)
        self.camera_grid.setColumnStretch(0, 1)
        self.camera_grid.setColumnStretch(1, 1)
        self.camera_tiles = {camera_id: CameraTile(camera_id, camera_id.value.upper()) for camera_id in CameraId}
        for camera_id, tile in self.camera_tiles.items():
            tile.activated.connect(self.toggle_camera_focus)
            self.camera_grid.addWidget(tile, *self.CAMERA_POSITIONS[camera_id])
        splitter.addWidget(self.camera_area)

        sidebar_content = QWidget()
        sidebar_content.setObjectName("central")
        sidebar = QVBoxLayout(sidebar_content)
        sidebar.setContentsMargins(5, 10, 10, 10)
        sidebar.setSpacing(8)
        self.gps_panel = GPSPanel()
        self.operator_panel = OperatorPanel()
        self.button_panel = ButtonPanel(config.provisional_button_actions)
        self.system_panel = SystemStatusPanel()
        self.network_panel = NetworkStatusPanel()
        self.event_log = EventLogPanel(config.ui.maximum_events)
        sidebar.addWidget(self.gps_panel)
        sidebar.addWidget(self.operator_panel)
        sidebar.addWidget(self.button_panel)
        sidebar.addWidget(self.system_panel)
        if config.ui.show_network_panel:
            sidebar.addWidget(self.network_panel)
        if config.ui.show_event_log:
            sidebar.addWidget(self.event_log)
        sidebar.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(sidebar_content)
        scroll.setMinimumWidth(410)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([1050, 550])
        root.addWidget(splitter, 1)
        self.bottom_bar = BottomBar()
        root.addWidget(self.bottom_bar)
        self.setCentralWidget(central)
        if self.mode == "WAN":
            self.top_bar.mode_label.setText("VISUALIZATION MODE · REAL WAN")
            self.bottom_bar.mode_label.setText("MODE WAN")
            self.operator_panel.hide()
            self.button_panel.hide()
            self.gps_panel.speed.unit.setText("MPH / GNSS")
            self.gps_panel.set_stream_state(DisplayState.NO_DATA)
            self.network_panel.badge.set_state("NO DATA")
            self.network_panel.values["video_age"].setToolTip("Onboard camera frame age reported by telemetry; not network latency")
            for name in self.system_panel.NAMES:
                if name not in ("CONTROL LINK", "OCI CONTROL RELAY", "GUI"):
                    self.system_panel.badges[name].set_state("NO DATA")
            self.system_panel.badges["GUI"].set_state("LIVE")
            for name in ("VIDEO", "GPS", "SYSTEM"):
                self.top_bar.badges[name].set_state("NO DATA")

        sources.frame_ready.connect(self.on_frame)
        sources.camera_status.connect(self.on_camera_status)
        sources.telemetry_ready.connect(self.on_telemetry)
        sources.telemetry_status.connect(self.on_telemetry_status)
        sources.telemetry_failed.connect(lambda detail: self._source_failure("GPS / telemetry", detail))
        sources.operator_ready.connect(self.on_operator)
        sources.operator_failed.connect(lambda detail: self._source_failure("operator mirror", detail))

        for key, camera_id in (("1", CameraId.FRONT), ("2", CameraId.LEFT), ("3", CameraId.RIGHT), ("4", CameraId.CABIN)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda selected=camera_id: self.maximize_camera(selected))
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.restore_camera_layout)
        QShortcut(QKeySequence(Qt.Key.Key_F12), self).activated.connect(self.capture_screenshot)

        self.metrics_timer = QTimer(self)
        self.metrics_timer.timeout.connect(self.refresh_metrics)
        self.metrics_timer.start(500)
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self._heartbeat)
        self.heartbeat_timer.start(100)
        self.event_log.add_event(f"Operator console initialized in {self.mode} mode")

    def start_sources(self) -> None:
        self.sources.start()
        self.event_log.add_event(f"Four independent {self.mode} camera readers started")
        self.event_log.add_event("GPS mock provider active" if self.mode == "MOCK" else "WAN telemetry subscriber started; no control mirror")

    @Slot(object)
    def on_frame(self, frame: VideoFrameState) -> None:
        tile = self.camera_tiles[frame.camera_id]
        first = tile.latest_sequence is None
        tile.update_frame(frame)
        if frame.camera_id is CameraId.FRONT:
            self.network_panel.values["resolution"].setText(f"{frame.width}×{frame.height}")
        self.system_panel.set_component(f"{frame.camera_id.value.upper()} CAMERA", frame.state)
        if first:
            self.event_log.add_event(f"{frame.camera_id.value.upper()} CAMERA connected · {self.mode}")

    @Slot(object, object, str)
    def on_camera_status(self, camera_id: CameraId, state: DisplayState, detail: str) -> None:
        self.camera_tiles[camera_id].set_stream_state(state)
        self.system_panel.set_component(f"{camera_id.value.upper()} CAMERA", state)
        self.event_log.add_event(f"{camera_id.value.upper()} · {state.value} · {detail}")

    @Slot(object)
    def on_telemetry_status(self, state):
        if self.mode == "WAN" and state is not DisplayState.LIVE:
            self.telemetry_summary.setText(f"TELEMETRY · {state.value}   |   GNSS · NO FRESH DATA   |   SYSTEM · --")
        self.system_panel.set_component("TELEMETRY", state)
        self.network_panel.badge.set_state(state.value)
        if self.mode == "WAN" and state is not DisplayState.LIVE:
            self.gps_panel.set_stream_state(state)
            self.system_panel.set_component("GPS", state)
            self.system_panel.set_component("ONBOARD COMPUTER", state)
            self.top_bar.badges["GPS"].set_state(state.value)
            self.top_bar.badges["SYSTEM"].set_state(state.value)
            for value in self.system_panel.values.values():
                value.setText("--")
        self.event_log.add_event(f"Telemetry · {state.value}")

    @Slot(object)
    def on_telemetry(self, state: TelemetryState) -> None:
        self.telemetry_updates += 1
        self.last_telemetry = state
        self.gps_panel.update_gps(state.gps)
        self.system_panel.set_component("GPS", state.gps.state)
        self.system_panel.update_health(state.health)
        self.system_panel.set_component("TELEMETRY", state.state)
        self.top_bar.badges["GPS"].set_state(state.gps.state.value)
        self.top_bar.badges["SYSTEM"].set_state(state.health.state.value)
        network = state.network
        if self.mode == "WAN":
            network = replace(network, resolution=self.camera_tiles[CameraId.FRONT].resolution_label.text(),
                              dropped_frames=sum(self.sources.dropped_before_render(role) for role in CameraId))
        self.network_panel.update_network(network)
        self.last_health = state.health
        if self.mode == "WAN":
            health = state.health
            cpu = "--" if health.cpu_percent is None else f"{health.cpu_percent:.1f}%"
            memory = "--" if health.memory_percent is None else f"{health.memory_percent:.1f}%"
            temperature = "--" if health.temperature_c is None else f"{health.temperature_c:.1f}°C"
            uptime = "--" if health.uptime_s is None else f"{health.uptime_s / 60:.1f} min"
            gnss = "NOT PUBLISHED" if not state.gps.published else state.gps.state.value
            self.telemetry_summary.setText(f"TELEMETRY · {state.state.value} {state.network.telemetry_hz:.1f} Hz / seq {state.sequence}   |   GNSS · {gnss}   |   JETSON CPU {cpu} / RAM {memory} / TEMP {temperature} / UP {uptime}")
        for camera_id, health in state.cameras.items():
            self.camera_tiles[camera_id].name_label.setToolTip(f"Onboard health: {health.healthy}; FPS: {health.fps}; frame age: {health.frame_age_s}")

    @Slot(object)
    def on_operator(self, state: OperatorState) -> None:
        self.operator_panel.update_operator(state)
        for pressed in self.button_panel.update_operator(state):
            action = self.config.provisional_button_actions[pressed]
            self.event_log.add_event(f"{pressed} pressed · provisional {action}")
        self._last_buttons = state.pressed_buttons

    def _source_failure(self, source_name: str, detail: str) -> None:
        self.event_log.add_event(f"{source_name} source unavailable · {detail}")

    def toggle_camera_focus(self, camera_id: CameraId) -> None:
        if self.maximized_camera == camera_id:
            self.restore_camera_layout()
        else:
            self.maximize_camera(camera_id)

    def maximize_camera(self, camera_id: CameraId) -> None:
        self.maximized_camera = camera_id
        for selected, tile in self.camera_tiles.items():
            tile.setVisible(selected == camera_id)
            tile.set_maximized(selected == camera_id)
        tile = self.camera_tiles[camera_id]
        self.camera_grid.addWidget(tile, 0, 0, 3, 2)
        self.event_log.add_event(f"{camera_id.value.upper()} CAMERA maximized")

    def restore_camera_layout(self) -> None:
        self.maximized_camera = None
        for camera_id, tile in self.camera_tiles.items():
            tile.setVisible(True)
            tile.set_maximized(False)
            self.camera_grid.addWidget(tile, *self.CAMERA_POSITIONS[camera_id])
        self.event_log.add_event("Multi-camera layout restored")

    def refresh_metrics(self) -> None:
        dropped = 0
        for camera_id, tile in self.camera_tiles.items():
            tile.refresh_metrics()
            dropped += max(tile.dropped_gui_frames, self.sources.dropped_before_render(camera_id))
            self.bottom_bar.update_camera(camera_id, tile.rendered_fps())
        telemetry_hz = self.telemetry_updates / max(1e-9, time.monotonic() - self.started_at)
        self.bottom_bar.update_rates(self.gps_panel.gps_rate(), telemetry_hz, dropped)
        self.process_cpu_samples.append(self._process.cpu_percent(interval=None))
        self.cpu_samples.append(psutil.cpu_percent(interval=None))
        rss = self._process.memory_info().rss
        self.rss_samples.append(rss)
        self.rss_timed_samples.append((time.monotonic() - self.started_at, rss))
        child_rss = child_cpu = 0
        current_children = self._process.children()
        for child in current_children:
            try:
                process = self._child_processes.setdefault(child.pid, child)
                child_rss += process.memory_info().rss
                child_cpu += process.cpu_percent(interval=None)
            except psutil.Error:
                pass
        self._child_processes = {p.pid: self._child_processes[p.pid] for p in current_children if p.pid in self._child_processes}
        self.child_rss_samples.append(child_rss)
        self.child_cpu_samples.append(child_cpu)
        states = [tile._stream_state for tile in self.camera_tiles.values()]
        video_state = DisplayState.LIVE if all(state is DisplayState.LIVE for state in states) else DisplayState.DEGRADED if DisplayState.LIVE in states else DisplayState.MOCK if self.mode == "MOCK" else DisplayState.NO_DATA
        self.top_bar.badges["VIDEO"].set_state(video_state.value)

    def _heartbeat(self) -> None:
        current = time.monotonic()
        self.gui_heartbeat_count += 1
        if current - self.started_at > 2.0:
            self.maximum_gui_timer_delay_s = max(self.maximum_gui_timer_delay_s, current - self._last_heartbeat - 0.1)
        self._last_heartbeat = current

    def capture_screenshot(self, output_path: str | Path | None = None) -> Path:
        if output_path is None:
            directory = Path("visualization/output/screenshots")
            directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            output_path = directory / f"operator_console_{timestamp}.png"
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.grab().save(str(path), "PNG")
        self.event_log.add_event(f"Screenshot saved · {path.name}")
        return path

    def metrics(self) -> dict[str, object]:
        if hasattr(self, "_close_metrics"):
            return {**self._close_metrics, "source_threads_running": self.sources.threads_running()}
        elapsed = max(1e-9, time.monotonic() - self.started_at)
        warm_rss = [rss for sample_time, rss in self.rss_timed_samples if sample_time >= 60.0]
        cameras = {
            camera_id.value: {
                "frames_rendered": tile.rendered_frames,
                "rendered_fps": tile.rendered_frames / elapsed,
                "sliding_fps": tile.rendered_fps(),
                "dropped_gui_frames": tile.dropped_gui_frames,
                "dropped_before_render": self.sources.dropped_before_render(camera_id),
                "last_sequence": tile.latest_sequence,
            }
            for camera_id, tile in self.camera_tiles.items()
        }
        return {
            "duration_s": elapsed,
            "cameras": cameras,
            "gps_updates": self.gps_panel.update_count,
            "gps_rate_hz": self.gps_panel.update_count / elapsed,
            "telemetry_updates": self.telemetry_updates,
            "telemetry_rate_hz": self.telemetry_updates / elapsed,
            "maximum_gui_timer_delay_s": self.maximum_gui_timer_delay_s,
            "gui_heartbeat_rate_hz": self.gui_heartbeat_count / elapsed,
            "cpu_percent_latest": self.cpu_samples[-1] if self.cpu_samples else None,
            "cpu_percent_mean": None if not self.cpu_samples else sum(self.cpu_samples) / len(self.cpu_samples),
            "cpu_percent_max": None if not self.cpu_samples else max(self.cpu_samples),
            "process_cpu_percent_mean": None if not self.process_cpu_samples else sum(self.process_cpu_samples) / len(self.process_cpu_samples),
            "process_cpu_percent_max": None if not self.process_cpu_samples else max(self.process_cpu_samples),
            "memory_percent_latest": psutil.virtual_memory().percent,
            "process_rss_bytes_latest": self.rss_samples[-1] if self.rss_samples else None,
            "process_rss_bytes_start": None if not self.rss_samples else self.rss_samples[0],
            "process_rss_bytes_min": None if not self.rss_samples else min(self.rss_samples),
            "process_rss_bytes_max": None if not self.rss_samples else max(self.rss_samples),
            "process_rss_growth_bytes": None if len(self.rss_samples) < 2 else self.rss_samples[-1] - self.rss_samples[0],
            "process_rss_growth_after_60s_bytes": None if len(warm_rss) < 2 else warm_rss[-1] - warm_rss[0],
            "source_threads_running": self.sources.threads_running(),
            "mode": self.mode,
            "decoder_rss_bytes_latest": self.child_rss_samples[-1] if self.child_rss_samples else None,
            "decoder_cpu_percent_mean": sum(self.child_cpu_samples)/len(self.child_cpu_samples) if self.child_cpu_samples else None,
            "video_source": self.sources.video.diagnostics() if hasattr(self.sources.video, "diagnostics") else {},
            "telemetry_source": self.sources.telemetry.diagnostics() if hasattr(self.sources.telemetry, "diagnostics") else {},
            "gps_displayed": self.gps_panel.values["lat"].text() != "--",
            "speed_displayed": self.gps_panel.speed.speed_mps is not None,
        }

    def closeEvent(self, event: QCloseEvent) -> None:
        self.metrics_timer.stop()
        self.heartbeat_timer.stop()
        self._close_metrics = self.metrics()
        self.sources.stop()
        event.accept()
