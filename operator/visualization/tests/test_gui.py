from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from visualization.gui.config import DEFAULT_ACTIONS, GuiConfig, load_gui_config
from visualization.gui.main_window import OperatorConsole
from visualization.gui.models.ui_state import CameraId, DisplayState, GPSState, HealthState, NetworkState, OperatorState, TelemetryState, VideoFrameState
from visualization.gui.sources.base import OperatorStateSource, TelemetrySource, VideoSource
from visualization.gui.sources.mock_operator_source import MockOperatorStateSource
from visualization.gui.sources.mock_telemetry_source import MockTelemetrySource
from visualization.gui.sources.mock_video_source import MockVideoSource
from visualization.gui.sources.workers import GuiSourceController
from visualization.gui.widgets.camera_tile import CameraTile
from visualization.gui.widgets.event_log import EventLogPanel


@pytest.fixture(scope="session")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def process_for(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def controller(video: VideoSource | None = None) -> GuiSourceController:
    return GuiSourceController(video or MockVideoSource(width=160, height=90), MockTelemetrySource(target_hz=20), MockOperatorStateSource(target_hz=30))


def window(video: VideoSource | None = None) -> OperatorConsole:
    return OperatorConsole(load_gui_config("visualization/config/gui.example.yaml"), controller(video))


def frame(camera_id: CameraId = CameraId.FRONT, sequence: int = 1, age_s: float = 0.0) -> VideoFrameState:
    return VideoFrameState(camera_id, np.zeros((90, 160, 3), dtype=np.uint8), sequence, "2026-01-01T00:00:00Z", time.monotonic() - age_s, 160, 90, 20.0, DisplayState.MOCK)


def gps(heading: float = 90.0, sequence: int = 1) -> GPSState:
    return GPSState(sequence, "2026-01-01T00:00:00Z", time.monotonic(), 35.0, -97.0, 5.0, heading, True, 9, 1.2, DisplayState.MOCK)


def operator(buttons: frozenset[str] = frozenset(), steering: float = 0.4, throttle: float = 0.6, brake: float = 0.2) -> OperatorState:
    return OperatorState(3, time.monotonic(), steering, throttle, brake, buttons, DisplayState.MOCK)


def test_gui_app_starts_four_workers_and_closes_cleanly(app: QApplication) -> None:
    console = window()
    console.show()
    console.start_sources()
    process_for(500)
    assert all(tile.rendered_frames > 0 for tile in console.camera_tiles.values())
    assert console.gps_panel.update_count > 0
    console.close()
    process_for(50)
    assert console.sources.threads_running() == 0


def test_camera_tile_updates_metrics(app: QApplication) -> None:
    tile = CameraTile(CameraId.FRONT, "FRONT")
    tile.resize(400, 240)
    tile.update_frame(frame(sequence=7))
    assert tile.latest_sequence == 7
    assert tile.rendered_frames == 1
    assert tile.resolution_label.text() == "160×90"
    assert tile.state_badge.text() == "MOCK"


def test_four_camera_mapping_is_exact(app: QApplication) -> None:
    console = window()
    assert set(console.camera_tiles) == set(CameraId)
    assert console.CAMERA_POSITIONS[CameraId.FRONT] == (0, 0, 1, 2)
    console.close()


def test_camera_maximize_and_restore(app: QApplication) -> None:
    console = window()
    console.maximize_camera(CameraId.CABIN)
    assert console.maximized_camera is CameraId.CABIN
    assert console.camera_tiles[CameraId.CABIN].isVisibleTo(console.camera_area)
    assert not console.camera_tiles[CameraId.FRONT].isVisibleTo(console.camera_area)
    console.restore_camera_layout()
    assert console.maximized_camera is None
    assert all(tile.isVisibleTo(console.camera_area) for tile in console.camera_tiles.values())
    console.close()


def test_gps_and_heading_update(app: QApplication) -> None:
    console = window()
    health = HealthState(5, 10, 1000, 12, DisplayState.MOCK, 10, 18, 10)
    network = NetworkState(18, 10, 0, 0, 0, "640×360")
    console.on_telemetry(TelemetryState(gps(heading=237.0), health, network))
    assert console.gps_panel.last_sequence == 1
    assert console.gps_panel.compass.heading_deg == 237.0
    assert console.gps_panel.speed.speed_mps == 5.0
    console.close()


def test_operator_gauges_update(app: QApplication) -> None:
    console = window()
    console.on_operator(operator(steering=-0.7, throttle=0.8, brake=0.3))
    assert console.operator_panel.steering.value == -0.7
    assert console.operator_panel.throttle.value == 0.8
    assert console.operator_panel.brake.value == 0.3
    console.close()


@pytest.mark.parametrize("button", ["L2", "L3", "R2", "R3", "TRIANGLE"])
def test_each_physical_button_indicator(app: QApplication, button: str) -> None:
    console = window()
    console.on_operator(operator(frozenset({button})))
    assert console.button_panel.cards[button].property("pressed") is True
    console.close()


def test_provisional_mapping_is_centralized_in_config(app: QApplication) -> None:
    config = load_gui_config("visualization/config/gui.example.yaml")
    assert config.provisional_button_actions == DEFAULT_ACTIONS
    console = OperatorConsole(config, controller())
    assert "PROVISIONAL" in console.button_panel.cards["L2"].action.text()
    assert "NEAR_LEFT" in console.button_panel.cards["L2"].action.text()
    console.close()


def test_stale_and_offline_camera_states(app: QApplication) -> None:
    tile = CameraTile(CameraId.FRONT, "FRONT")
    tile.update_frame(frame(age_s=3.0))
    tile.refresh_metrics()
    assert tile.state_badge.text() == "STALE"
    tile.set_stream_state(DisplayState.OFFLINE)
    assert tile.state_badge.text() == "OFFLINE"


def test_event_log_is_bounded(app: QApplication) -> None:
    log = EventLogPanel(max_events=5)
    for index in range(20):
        log.add_event(f"event {index}")
    assert log.list.count() == 5
    assert "event 19" in log.list.item(0).text()


class OneCameraFailureSource(MockVideoSource):
    def next_frame(self, camera_id: CameraId) -> VideoFrameState:
        if camera_id is CameraId.LEFT:
            raise RuntimeError("simulated isolated camera failure")
        return super().next_frame(camera_id)


def test_one_camera_failure_does_not_freeze_gui_or_other_cameras(app: QApplication) -> None:
    console = window(OneCameraFailureSource(width=160, height=90))
    console.show()
    console.start_sources()
    process_for(500)
    assert console.camera_tiles[CameraId.LEFT].state_badge.text() == "OFFLINE"
    assert console.camera_tiles[CameraId.FRONT].rendered_frames > 2
    assert console.maximum_gui_timer_delay_s < 1.0
    console.close()


class FailingTelemetrySource(MockTelemetrySource):
    def get_latest(self) -> TelemetryState:
        raise RuntimeError("simulated GPS failure")


def test_gps_failure_does_not_stop_camera_rendering(app: QApplication) -> None:
    source_controller = GuiSourceController(MockVideoSource(width=160, height=90), FailingTelemetrySource(), MockOperatorStateSource())
    console = OperatorConsole(load_gui_config("visualization/config/gui.example.yaml"), source_controller)
    console.show()
    console.start_sources()
    process_for(400)
    assert console.camera_tiles[CameraId.FRONT].rendered_frames > 2
    assert any("GPS / telemetry source unavailable" in console.event_log.list.item(index).text() for index in range(console.event_log.list.count()))
    console.close()


def test_mock_sources_implement_adapter_contracts() -> None:
    assert isinstance(MockVideoSource(), VideoSource)
    assert isinstance(MockTelemetrySource(), TelemetrySource)
    assert isinstance(MockOperatorStateSource(), OperatorStateSource)


def test_screenshot_capability(app: QApplication, tmp_path) -> None:
    console = window()
    console.show()
    process_for(50)
    path = console.capture_screenshot(tmp_path / "console.png")
    assert path.is_file()
    assert path.stat().st_size > 1000
    console.close()


def test_gui_source_controller_has_no_running_threads_after_close(app: QApplication) -> None:
    console = window()
    console.start_sources()
    process_for(200)
    console.close()
    assert console.sources.threads_running() == 0
