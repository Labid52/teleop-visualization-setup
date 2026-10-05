"""Reader adapters tested with dummy secrets and deterministic failure injection."""

from dataclasses import replace
import json
import base64
import sys
import threading
import os
from pathlib import Path
import time

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QEventLoop, QTimer

from visualization.gui.main import build_demo_console, build_wan_console, build_minimal_wan_console
from visualization.gui.minimal_window import MinimalGpsPanel, MinimalOperatorConsole
from visualization.gui.widgets.speedometer import SpeedometerWidget
from visualization.gui.models.ui_state import CameraId, DisplayState, GPSState, VideoFrameState
from visualization.gui.sources.bmp_stream import BmpFrameBuffer
from visualization.gui.sources.wan_config import WanCredentials, READER_VARIABLES, load_wan_credentials
from visualization.gui.sources.wan_telemetry_source import subscriber_auth, validate_message, map_telemetry, WanTelemetrySource
from visualization.gui.sources.wan_video_source import WanVideoSource
from visualization.gui.sources.workers import GuiSourceController
from visualization.gui.sources.no_operator_source import NoOperatorStateSource
from visualization.gui.config import load_gui_config
from visualization.gui.main_window import OperatorConsole
from visualization.gui.sources.decoder_selection import select_srt_decoder


@pytest.fixture
def credentials():
    return WanCredentials("example.invalid", username="dummy-reader", password="dummy-password", passphrases={role: "dummy-passphrase" for role in CameraId}, subscriber_token="dummy-token")


def test_decoder_skips_path_first_binary_without_srt(tmp_path, monkeypatch, credentials):
    bad_dir, good_dir = tmp_path / "conda", tmp_path / "system"
    bad_dir.mkdir()
    good_dir.mkdir()
    for directory, protocols in ((bad_dir, "Input: srtp udp"), (good_dir, "Input: srt udp")):
        executable = directory / "ffmpeg"
        executable.write_text(f"#!{sys.executable}\nprint({protocols!r})\n")
        executable.chmod(0o700)
    monkeypatch.setenv("PATH", os.pathsep.join((str(bad_dir), str(good_dir))))
    source = WanVideoSource(credentials)
    assert source.executable == str(good_dir / "ffmpeg")


def test_explicit_decoder_without_srt_rejected(tmp_path):
    executable = tmp_path / "unsupported_ffmpeg"
    executable.write_text(f"#!{sys.executable}\nprint('Input: srtp udp')\n")
    executable.chmod(0o700)
    with pytest.raises(ValueError, match="supports SRT"):
        select_srt_decoder(str(executable))


def message(sequence=1):
    return {"schema_version": 1, "message_type": "vehicle_visualization", "sequence": sequence,
            "timestamp_utc": f"2026-01-01T00:00:{sequence:02d}Z", "timestamp_monotonic_s": float(sequence),
            "gnss": {"latitude_deg": 1.0, "longitude_deg": 2.0, "fix_valid": True, "horizontal_speed_mps": 3.0},
            "cameras": {"front": {"stream_path": "front", "healthy": True, "fps": 20, "last_frame_age_s": .01}},
            "system": {"cpu_percent": 12, "memory_percent": 30, "uptime_s": 100, "telemetry_rate_hz": 10}}


@pytest.mark.parametrize("role", list(CameraId))
def test_role_reader_contract(credentials, role):
    uri = credentials.reader_uri(role)
    assert f"streamid=read:{role.value}:dummy-reader:dummy-password" in uri
    assert "pbkeylen=32" in uri and "passphrase=dummy-passphrase" in uri
    assert "latency" not in uri


def test_credentials_private_and_reader_only(tmp_path, credentials):
    path = tmp_path / "reader.env"
    values = {key: "dummy" for key in READER_VARIABLES}
    values.update(OCI_VISUALIZATION_HOST="example.invalid", SRT_PORT="8890", TELEMETRY_PORT="8767")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    path.chmod(0o600)
    loaded = load_wan_credentials(path)
    assert loaded.host == "example.invalid"
    assert "dummy-password" not in repr(credentials)
    path.chmod(0o644)
    with pytest.raises(ValueError):
        load_wan_credentials(path)


def test_subscriber_auth():
    assert json.loads(subscriber_auth("dummy-token")) == {"type": "auth", "role": "subscriber", "token": "dummy-token"}


@pytest.mark.parametrize("raw", ['{}', '[]', 'not JSON', '{"schema_version":1,"message_type":"vehicle_visualization","x":NaN}', '{"schema_version":1,"message_type":"vehicle_visualization","x":1e999}', '{"schema_version":1,"message_type":"CMD"}', '{"schema_version":true,"message_type":"vehicle_visualization"}'])
def test_bad_schema_and_nonfinite(raw):
    with pytest.raises(ValueError):
        validate_message(raw)


def test_optional_heading_and_missing_system():
    with pytest.raises(ValueError):
        validate_message(json.dumps({"schema_version": 1, "message_type": "vehicle_visualization", "text": "😀" * 17000}, ensure_ascii=False))
    state = map_telemetry(message(), time.monotonic(), 10)
    assert state.gps.heading_deg is None and state.gps.heading_source == "UNAVAILABLE"
    assert state.gps.speed_mps == 3 and state.gps.fix_valid
    assert state.cameras[CameraId.FRONT].healthy
    minimal = map_telemetry({"schema_version": 1, "message_type": "vehicle_visualization"}, time.monotonic(), 0)
    assert minimal.gps.state is DisplayState.NO_DATA
    assert minimal.health.cpu_percent is None
    oversized = message()
    oversized["system"]["cpu_percent"] = 10**400
    assert map_telemetry(oversized, time.monotonic(), 10).health.cpu_percent is None


def test_bmp_fragmentation_and_bound():
    _, encoded = cv2.imencode(".bmp", np.zeros((10, 20, 3), np.uint8))
    raw = encoded.tobytes()
    buffer = BmpFrameBuffer()
    buffer.append(raw[:30])
    assert buffer.pop() is None
    buffer.append(raw[30:] + raw)
    assert buffer.pop() == raw and buffer.pop() == raw
    assert len(buffer) == 0
    with pytest.raises(ValueError):
        buffer.append(b"x" * (buffer.maximum_bytes + 1))


class FakeConnection:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.closed = False
    def send(self, raw):
        assert json.loads(raw)["role"] == "subscriber"
    def recv(self, timeout):
        return next(self.messages)
    def close(self):
        self.closed = True


def test_telemetry_latest_repeats_reconnect(credentials):
    connections = []
    def connector(*args, **kwargs):
        connection = FakeConnection([json.dumps({"type": "auth_ok", "role": "subscriber"}), json.dumps(message(1)), json.dumps(message(1)), "bad", json.dumps(message(2))])
        connections.append(connection)
        return connection
    source = WanTelemetrySource(credentials, connector=connector)
    assert source.get_latest() is None
    assert source.status() is DisplayState.NO_DATA
    assert source.get_latest() is None
    assert source.get_latest() is None
    assert source.get_latest().sequence == 2
    assert source.repeats == 1 and source.malformed == 1
    assert source.get_latest() is None
    assert source.status() is DisplayState.DISCONNECTED
    source._next_attempt = 0
    assert source.get_latest() is None
    assert source.reconnects == 1 and connections[0].closed
    source._state = DisplayState.LIVE
    source._last_progress = time.monotonic() - 10
    assert source.status() is DisplayState.STALE
    source.stop()
    assert connections[-1].closed


def test_auth_rejection(credentials):
    source = WanTelemetrySource(credentials, connector=lambda *args, **kw: FakeConnection(['{"type":"error"}']))
    assert source.get_latest() is None
    assert not source.authentications
    source.stop()


def test_wan_console_all_roles_no_mock_controls(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "private.env"
    values = {key: "dummy" for key in READER_VARIABLES}
    values.update(OCI_VISUALIZATION_HOST="example.invalid", SRT_PORT="8890", TELEMETRY_PORT="8767")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    path.chmod(0o600)
    console = build_wan_console("visualization/config/gui.example.yaml", str(path))
    assert console.mode == "WAN"
    assert console.sources.video.camera_ids() == tuple(CameraId)
    assert console.operator_panel.isHidden() and console.button_panel.isHidden()
    assert console.gps_panel.compass.heading_deg is None
    assert console.gps_panel.speed.speed_mps is None
    assert console.top_bar.badges["CONTROL"].text() == "--"
    console.close()


def test_minimal_wan_selects_cabin_only_and_preserves_full_mode(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "private.env"
    values = {key: "dummy" for key in READER_VARIABLES}
    values.update(OCI_VISUALIZATION_HOST="example.invalid", SRT_PORT="8890", TELEMETRY_PORT="8767")
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    path.chmod(0o600)
    minimal = build_minimal_wan_console(str(path), "/usr/bin/ffmpeg")
    assert minimal.sources.video.camera_ids() == (CameraId.CABIN,)
    minimal.close()
    full = build_wan_console("visualization/config/gui.example.yaml", str(path), "/usr/bin/ffmpeg")
    assert set(full.sources.video.camera_ids()) == set(CameraId)
    full.close()


def test_minimal_premium_branding_and_graphics():
    app = QApplication.instance() or QApplication([])
    from visualization.gui.sources.mock_video_source import MockVideoSource
    from visualization.gui.sources.mock_telemetry_source import MockTelemetrySource
    source = GuiSourceController(MockVideoSource(width=640, height=480, enabled={CameraId.CABIN}), MockTelemetrySource(), NoOperatorStateSource())
    console = MinimalOperatorConsole(source)
    assert console.windowTitle() == "MILA · REMOTE VEHICLE OPERATOR CONSOLE"
    visible_text = " ".join(label.text() for label in console.findChildren(QLabel))
    assert "MINIMAL WAN" not in visible_text
    assert "TELEMETRY LIVE" not in visible_text
    assert console.sources.video.camera_ids() == (CameraId.CABIN,)
    assert console.cabin.image_label.sizePolicy().hasHeightForWidth() is False
    assert isinstance(console.speedometer, SpeedometerWidget)
    console.resize(1400, 900)
    assert console.width() == 1400 and console.height() == 900
    console.close()


def test_minimal_gps_converts_mps_to_mph_and_does_not_require_heading():
    panel = MinimalGpsPanel()
    gps = GPSState(1, "2026-01-01T00:00:00Z", time.monotonic(), 35.0, -97.0, 10.0, None, True, 8, 2.0, DisplayState.LIVE, "UNAVAILABLE")
    panel.update_state(gps)
    assert panel.values["speed"].text() == "22.4 mph"
    assert panel.values["fix"].text() == "VALID"
    panel.close()


def test_minimal_gps_handles_absent_gnss_without_imu_or_health():
    panel = MinimalGpsPanel()
    gps = GPSState(2, "", time.monotonic(), None, None, None, None, False, None, None, DisplayState.NO_DATA, "UNAVAILABLE", False)
    panel.update_state(gps)
    assert panel.state_badge.text() == "NO DATA"
    assert panel.values["fix"].text() == "GNSS NOT PUBLISHED"
    panel.close()


def test_minimal_gps_retains_last_fix_as_stale_when_gnss_temporarily_absent():
    panel = MinimalGpsPanel()
    now = time.monotonic()
    panel.update_state(GPSState(1, "", now, 35.0, -97.0, 4.0, None, True, 8, 2.0, DisplayState.LIVE, "UNAVAILABLE"))
    panel.update_state(GPSState(2, "", now + 0.5, None, None, None, None, False, None, None, DisplayState.NO_DATA, "UNAVAILABLE", False))
    assert panel.state_badge.text() == "STALE"
    assert panel.values["latitude"].text() == "35.000000°"
    assert panel.values["longitude"].text() == "-97.000000°"
    assert panel.values["fix"].text() == "STALE — GNSS UNAVAILABLE"
    panel.close()


def test_camera_failure_is_independent(credentials):
    source = WanVideoSource(credentials)
    source._sessions[CameraId.FRONT].state = DisplayState.LIVE
    source._sessions[CameraId.FRONT].last_frame = time.monotonic()
    source._sessions[CameraId.LEFT].state = DisplayState.WAITING
    assert source.camera_status(CameraId.FRONT)[0] is DisplayState.LIVE
    assert source.camera_status(CameraId.LEFT)[0] is DisplayState.WAITING
    assert source.camera_ids() == tuple(CameraId)


def test_missing_gnss_keeps_health_visible_without_fake_gps_updates(credentials):
    app = QApplication.instance() or QApplication([])
    source = WanVideoSource(credentials, enabled=set())
    console = OperatorConsole(load_gui_config("visualization/config/gui.example.yaml"),
        GuiSourceController(source, WanTelemetrySource(credentials), NoOperatorStateSource()))
    raw = message(2)
    raw.pop("gnss", None)
    raw["system"] = {"cpu_percent": 18.1, "memory_percent": 6.0, "temperature_c": 52.1, "uptime_s": 1481, "telemetry_rate_hz": 9.6}
    state = map_telemetry(raw, time.monotonic(), 9.6)
    console.on_telemetry(state)
    assert not state.gps.published
    assert console.gps_panel.update_count == 0
    assert console.gps_panel.values["fix"].text() == "GNSS NOT PUBLISHED"
    assert console.gps_panel.values["age"].text() == "--"
    assert console.gps_panel.values["rate"].text() == "--"
    assert "LIVE 9.6 Hz" in console.telemetry_summary.text()
    assert "CPU 18.1%" in console.telemetry_summary.text()
    assert "TEMP 52.1°C" in console.telemetry_summary.text()
    assert not console.telemetry_summary.isHidden()
    console.on_telemetry_status(DisplayState.STALE)
    assert "NO FRESH DATA" in console.telemetry_summary.text()
    assert "CPU 18.1%" not in console.telemetry_summary.text()
    console.close()


def test_gnss_can_appear_after_health_only_message():
    from visualization.gui.widgets.gps_panel import GPSPanel
    app = QApplication.instance() or QApplication([])
    panel = GPSPanel()
    raw = message(1)
    without_gnss = {key: value for key, value in raw.items() if key != "gnss"}
    panel.update_gps(map_telemetry(without_gnss, time.monotonic(), 10).gps)
    panel.update_gps(map_telemetry(raw, time.monotonic(), 10).gps)
    assert panel.update_count == 1
    assert panel.values["fix"].text() != "GNSS NOT PUBLISHED"
    panel.close()


def test_decoder_process_reconnect_and_stop(tmp_path, credentials):
    _, image = cv2.imencode(".bmp", np.zeros((32, 64, 3), np.uint8))
    executable = tmp_path / "fake_decoder"
    executable.write_text(f"#!{sys.executable}\nimport sys,time,base64\nif '-protocols' in sys.argv:\n print('Input: srt')\n sys.exit(0)\nimage=base64.b64decode({base64.b64encode(image).decode()!r})\nfor _ in range(3):\n sys.stdout.buffer.write(image)\n sys.stdout.buffer.flush()\n time.sleep(.02)\n")
    executable.chmod(0o700)
    source = WanVideoSource(credentials, enabled={CameraId.FRONT}, executable=str(executable))
    source.start_camera(CameraId.FRONT)
    frames = []
    deadline = time.monotonic() + 5
    while len(frames) < 6 and time.monotonic() < deadline:
        frame = source.next_frame(CameraId.FRONT)
        if frame is not None:
            frames.append(frame)
    assert len(frames) == 6
    assert frames[-1].sequence == 6
    assert frames[-1].width == 64 and frames[-1].height == 32
    assert source.diagnostics()["front"]["reconnects"] >= 1
    source.stop_camera(CameraId.FRONT)
    assert source._sessions[CameraId.FRONT].process is None


def test_gui_missing_heading_offline_resize_and_latest_state():
    app = QApplication.instance() or QApplication([])
    console = build_demo_console("visualization/config/gui.example.yaml")
    state = map_telemetry(message(), time.monotonic(), 10)
    console.on_telemetry(state)
    assert console.gps_panel.compass.heading_deg is None
    assert console.gps_panel.speed.speed_mps == 3
    pixels = np.zeros((30, 40, 3), np.uint8)
    pixels[0, 0] = (10, 20, 30)
    frame = VideoFrameState(CameraId.FRONT, pixels, 1, "", time.monotonic(), 40, 30, 20, DisplayState.LIVE)
    console.on_frame(frame)
    color = console.camera_tiles[CameraId.FRONT]._image.pixelColor(0, 0)
    assert (color.red(), color.green(), color.blue()) == (30, 20, 10)
    console.on_camera_status(CameraId.LEFT, DisplayState.WAITING, "retry")
    assert console.camera_tiles[CameraId.FRONT]._image is not None
    console.on_camera_status(CameraId.FRONT, DisplayState.DISCONNECTED, "retry")
    console.camera_tiles[CameraId.FRONT].resize(300, 200)
    assert console.camera_tiles[CameraId.FRONT]._image is None
    console.camera_tiles[CameraId.FRONT].set_stream_state(DisplayState.LIVE)
    assert console.camera_tiles[CameraId.FRONT]._stream_state is not DisplayState.LIVE
    assert console.camera_tiles[CameraId.LEFT].image_label.text() == "WAITING FOR STREAM"
    for sequence in range(100):
        console.sources._store_latest_telemetry(replace(state, sequence=sequence))
        console.sources._store_latest_frame(replace(frame, sequence=sequence))
    assert console.sources._latest_telemetry.sequence == 99
    assert len(console.sources._latest_frames) == 1
    assert console.sources.dropped_before_render(CameraId.FRONT) == 99
    console.sources._deliver_latest_frames()
    assert console.last_telemetry.sequence == 99
    console.close()
    assert console.metrics()["source_threads_running"] == 0


def test_healthy_injected_wan_sources_render_concurrently(tmp_path, credentials):
    """Exercise real adapter/Qt wiring with controlled local decoder output, not WAN evidence."""
    app = QApplication.instance() or QApplication([])
    _, image = cv2.imencode(".bmp", np.zeros((32, 64, 3), np.uint8))
    executable = tmp_path / "timed_decoder"
    executable.write_text(f"#!{sys.executable}\nimport sys,time,base64\nif '-protocols' in sys.argv:\n print('Input: srt')\n sys.exit(0)\nimage=base64.b64decode({base64.b64encode(image).decode()!r})\nwhile True:\n sys.stdout.buffer.write(image)\n sys.stdout.buffer.flush()\n time.sleep(.05)\n")
    executable.chmod(0o700)

    class TimedConnection:
        def __init__(self):
            self.sequence = 0
            self.next_time = time.monotonic()
            self.closed = threading.Event()
            self.ack = True
        def send(self, raw):
            assert json.loads(raw)["role"] == "subscriber"
        def recv(self, timeout):
            if self.ack:
                self.ack = False
                return json.dumps({"type": "auth_ok", "role": "subscriber"})
            delay = self.next_time - time.monotonic()
            if delay > timeout:
                self.closed.wait(timeout)
                raise TimeoutError
            self.closed.wait(max(0, delay))
            self.sequence += 1
            self.next_time = time.monotonic() + .1
            return json.dumps(message(self.sequence))
        def close(self):
            self.closed.set()

    source = WanVideoSource(credentials, executable=str(executable))
    telemetry = WanTelemetrySource(credentials, connector=lambda *a, **k: TimedConnection())
    controller = GuiSourceController(source, telemetry, NoOperatorStateSource())
    console = OperatorConsole(load_gui_config("visualization/config/gui.example.yaml"), controller)
    console.show()
    console.start_sources()
    loop = QEventLoop()
    QTimer.singleShot(1800, loop.quit)
    loop.exec()
    assert all(tile.rendered_frames >= 15 for tile in console.camera_tiles.values())
    assert console.telemetry_updates >= 8
    assert console.gps_panel.speed.speed_mps == 3
    assert console.gps_panel.values["lat"].text() != "--"
    assert console.gps_panel.compass.heading_deg is None
    assert telemetry.status() is DisplayState.LIVE
    console.close()
    assert controller.threads_running() == 0
