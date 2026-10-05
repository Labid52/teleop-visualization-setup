"""Geometry, stale-data semantics, isolated navigation and presentation contracts."""
from dataclasses import replace
from pathlib import Path
import time

import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLabel

from visualization.gui.main import build_minimal_demo_console
from visualization.gui.minimal_window import MinimalGpsPanel
from visualization.gui.models.navigation import CourseEstimator, distance_and_bearing
from visualization.gui.models.ui_state import CameraId, DisplayState, GPSState, VideoFrameState
from visualization.gui.widgets.online_map import OnlineMapWidget
from visualization.gui.widgets.premium_video import StatusPill
from visualization.gui.widgets.speedometer import SpeedometerWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def settle(ms=60):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()


def fix(**kwargs):
    gps=GPSState(1,"2026-09-17T12:00:00Z",time.monotonic(),35.,-97.,5.,None,True,9,1.,DisplayState.LIVE)
    return replace(gps,**kwargs)


@pytest.fixture
def console(app):
    result=build_minimal_demo_console("visualization/config/gui.example.yaml")
    yield result
    result.close();settle()


@pytest.mark.parametrize("size",[(1080,740),(1280,800),(1920,1080)])
def test_true_four_three_viewport_and_stable_controls(console,size):
    console.resize(*size);console.show();settle()
    view=console.cabin.image_label
    assert abs(view.width()/view.height()-4/3)<.006
    frame=VideoFrameState(CameraId.CABIN,np.zeros((480,640,3),np.uint8),1,"",time.monotonic(),640,480,10,DisplayState.LIVE)
    console.on_frame(frame);settle()
    rect=view.image_rect()
    assert abs(rect.width()/rect.height()-4/3)<.006
    assert abs(rect.width()-view.width())<=2 and abs(rect.height()-view.height())<=2
    assert console.cabin.state_badge.size().toTuple()==(112,28)
    assert console.cabin.maximize_button.size().toTuple()==(52,28)
    assert console.map.height()>=180
    assert console.speedometer.height()>=130
    assert console.body.rect().contains(console.body.right.geometry())


def test_focus_and_fullscreen_preserve_geometry(console):
    console.show();settle();console.toggle_camera_focus();settle()
    assert console.body.right.isHidden() and console.speed_panel.isHidden()
    assert abs(console.cabin.image_label.width()/console.cabin.image_label.height()-4/3)<.006
    console.toggle_fullscreen();settle()
    assert console.isFullScreen()
    assert console.cabin.state_badge.height()==28
    console.restore_view();settle()
    assert not console.isFullScreen() and not console.body.focus


def test_premium_branding_and_information_hierarchy(console):
    console.show();settle()
    visible=" ".join(w.text() for w in console.findChildren(QLabel) if w.isVisible())
    for forbidden in ("MINIMAL WAN","SENDER-SIDE","TELEMETRY LIVE","CABIN + GNSS"):
        assert forbidden not in visible.upper()
    assert console.windowTitle()=="MILA · REMOTE VEHICLE OPERATOR CONSOLE"
    assert console.gps.values["latitude"].font().pixelSize()>=28
    assert console.gps.values["longitude"].font().pixelSize()>=28
    assert console.sources.video.camera_ids()==(CameraId.CABIN,)
    assert not hasattr(console,"system_panel")


def test_badges_never_change_size(app):
    badge=StatusPill()
    for state in ("LIVE","STALE","NO DATA","RECONNECTING","READY"):
        badge.set_state(state);badge.show();settle(2)
        assert badge.size().toTuple()==(112,28)
    badge.close()


def test_speed_zero_unknown_and_noise(app):
    gauge=SpeedometerWidget()
    gauge.set_speed_mps(10);assert gauge.speed_mph==pytest.approx(22.36936)
    gauge.set_speed_mps(0);assert gauge.speed_mph==0
    gauge.set_speed_mps(.03);assert gauge.speed_mph==0
    gauge.set_speed_mps(None);assert gauge.speed_mph is None
    gauge.close()


def test_course_ignores_imu_and_stationary_noise():
    estimator=CourseEstimator()
    estimator.update(fix(heading_deg=210,heading_source="XSENS IMU"))
    assert estimator.heading is None
    estimator.update(fix(heading_deg=90,heading_source="GNSS COG"))
    assert estimator.heading==90
    estimator.update(fix(speed_mps=.02,heading_deg=270,heading_source="GNSS COG",latitude=35.000001))
    assert estimator.heading==90


def test_course_accumulates_displacement_above_accuracy_threshold():
    estimator=CourseEstimator();estimator.update(fix())
    for i in range(1,5):estimator.update(fix(longitude=-97+i*.000003))
    assert estimator.heading is None
    estimator.update(fix(longitude=-96.9999))
    assert estimator.heading==pytest.approx(90,abs=.01)
    assert distance_and_bearing((35,-97),(35,-96.9999))[0]>8


def test_gps_stale_age_keeps_advancing_and_eventually_expires(app,monkeypatch):
    panel=MinimalGpsPanel();start=time.monotonic();panel.update_state(fix(timestamp_monotonic_s=start))
    monkeypatch.setattr("visualization.gui.minimal_window.time.monotonic",lambda:start+4)
    panel.refresh_age();assert panel.state=="STALE"
    assert "4.0" in panel.values["age"].text()
    monkeypatch.setattr("visualization.gui.minimal_window.time.monotonic",lambda:start+8)
    panel.update_state(fix(timestamp_monotonic_s=start+8)) # same UTC: cache is not fresh
    assert panel.state=="STALE" and panel.age_s==pytest.approx(8)
    monkeypatch.setattr("visualization.gui.minimal_window.time.monotonic",lambda:start+31)
    panel.refresh_age();assert panel.state=="NO DATA"
    assert panel.values["latitude"].text()=="—"
    panel.close()


def test_unavailable_map_does_not_break_gnss(console):
    from visualization.gui.sources.wan_telemetry_source import map_telemetry
    raw={"sequence":1,"timestamp_utc":"2026-09-17T12:00:00Z","gnss":{
        "latitude_deg":35.12,"longitude_deg":-97.1,"horizontal_speed_mps":2,
        "fix_valid":True,"satellite_count":11,"horizontal_accuracy_m":2.3}}
    console.map.engine_error="unavailable"
    state=map_telemetry(raw,time.monotonic(),10);console.on_telemetry(state)
    assert console.gps.values["latitude"].text()=="35.120000°"
    assert console.map.latitude==35.12
    assert console.gps.values["satellites"].text()=="◈  11"
    assert console.gps.values["accuracy"].text()=="±2.3 m"
    assert console.speedometer.speed_mph==pytest.approx(4.473872)


def test_old_video_and_gnss_not_shown_live(console):
    frame=VideoFrameState(CameraId.CABIN,np.zeros((480,640,3),np.uint8),1,"",time.monotonic()-4,640,480,10,DisplayState.LIVE)
    console.on_frame(frame);console.refresh()
    assert console.cabin.image_label.image is None
    assert console.video_badge.text()=="STALE"
    console.on_telemetry_status(DisplayState.DISCONNECTED)
    assert console.gps.state=="NO DATA"


def test_map_bridge_has_one_latest_slot_and_no_secret_or_telemetry_object(app):
    widget=OnlineMapWidget(web_enabled=False)
    for i in range(100):widget.update_position(35+i*.000001,-97,90)
    assert widget._latest=={"lat":35.000099,"lon":-97,"course":90,"stale":False}
    assert widget.web is None
    script=Path("visualization/gui/assets/navigation.js").read_text()
    assert 'marker:"triangle"' in script
    assert 'rotationAlignment:"map"' in script
    assert 'map.easeTo' in script and 'pitch:48' in script
    assert 'fill-extrusion' in script
    widget.shutdown();widget.close()
