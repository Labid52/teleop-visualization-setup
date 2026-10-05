"""Two-camera composition preserves approved GNSS and instrument behavior."""
from pathlib import Path
import time

import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QLabel

from visualization.gui.main import build_two_camera_demo_console, build_two_camera_wan_console, build_minimal_demo_console
from visualization.gui.models.ui_state import CameraId, DisplayState, VideoFrameState
from visualization.gui.sources.wan_config import WanCredentials
from visualization.gui.widgets.button_guide import ButtonGuideImage


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def settle():
    loop=QEventLoop();QTimer.singleShot(60,loop.quit);loop.exec()


@pytest.fixture
def console(app):
    window=build_two_camera_demo_console('visualization/config/gui.example.yaml')
    yield window
    window.close();settle()


def frame(role):
    return VideoFrameState(role,np.zeros((480,640,3),np.uint8),1,'',time.monotonic(),640,480,10,DisplayState.LIVE)


@pytest.mark.parametrize('size',[(1360,860),(1360,900),(1920,1066)])
def test_larger_equal_four_three_tiles_and_readable_right_side(console,size):
    original=build_minimal_demo_console('visualization/config/gui.example.yaml')
    original.resize(*size);original.show()
    console.resize(*size);console.show();settle()
    assert console.body.right.height()==original.body.right.height()
    assert console.body.right.width()>=480
    assert console.front.width()>(original.body.left.width()-14)/2*1.08
    assert console.speed_panel.height()>=300
    if size[0]>=1920:
        previous_width=min(round(original.body.left.width()*1.12),round(console.body.width()*.54))
        previous_camera=round((((previous_width-14)//2)-4)*3/4)+70
        previous_speed=console.body.height()-previous_camera-14
        assert console.speed_panel.height()==pytest.approx(previous_speed*.70,abs=2)
    for role,tile in console.tiles.items():
        console.on_frame(frame(role));settle()
        view=tile.image_label;rect=view.image_rect()
        assert abs(view.width()/view.height()-4/3)<.006
        assert abs(rect.width()-view.width())<=2
        assert abs(rect.height()-view.height())<=2
        assert tile.state_badge.size().toTuple()==(112,28)
        assert tile.maximize_button.size().toTuple()==(52,28)
        assert tile.rect().contains(tile.maximize_button.mapTo(tile,tile.maximize_button.rect().bottomRight()))
    assert abs(console.front.width()-console.cabin.width())<=1
    assert console.front.geometry().right()<console.cabin.geometry().left()
    assert console.speedometer.isVisible() and console.map.isVisible()
    original.close();settle()


def test_only_required_roles_and_independent_states(console):
    assert console.sources.video.camera_ids()==(CameraId.FRONT,CameraId.CABIN)
    console.on_frame(frame(CameraId.FRONT));console.on_frame(frame(CameraId.CABIN))
    console.on_camera_status(CameraId.FRONT,DisplayState.DISCONNECTED,'')
    assert console.front.image_label.image is None
    assert console.cabin.image_label.image is not None
    assert console.cabin._stream_state=='LIVE'
    console.on_frame(frame(CameraId.FRONT))
    console.on_camera_status(CameraId.CABIN,DisplayState.OFFLINE,'')
    assert console.front._stream_state=='LIVE'
    assert console.cabin._stream_state=='NO VIDEO'


def test_each_camera_focus_and_restore(console):
    console.show();settle()
    for role in (CameraId.FRONT,CameraId.CABIN):
        console.toggle_camera_focus(role);settle()
        assert console.tiles[role].isVisible()
        assert not console.tiles[CameraId.CABIN if role==CameraId.FRONT else CameraId.FRONT].isVisible()
        assert abs(console.tiles[role].image_label.width()/console.tiles[role].image_label.height()-4/3)<.01
        console.restore_view();settle()
        assert all(tile.isVisible() for tile in console.tiles.values())


def test_branding_and_existing_one_camera_mode(console):
    console.show();settle()
    text=' '.join(label.text() for label in console.findChildren(QLabel) if label.isVisible())
    for forbidden in ('LEFT','RIGHT CAMERA','MINIMAL WAN','TWO CAMERA MODE'):
        assert forbidden not in text
    assert 'FRONT' in text and 'CABIN' in text
    assert console.windowTitle()=='MILA · REMOTE VEHICLE OPERATOR CONSOLE'
    original=build_minimal_demo_console('visualization/config/gui.example.yaml')
    assert original.sources.video.camera_ids()==(CameraId.CABIN,)
    original.close()


def test_button_guide_is_opt_in_and_confined_to_speed_panel(app):
    plain=build_two_camera_demo_console('visualization/config/gui.example.yaml')
    guided=build_two_camera_demo_console('visualization/config/gui.example.yaml',show_button=True)
    assert plain.button_guide is None
    assert guided.button_guide is not None and guided.button_guide.image_loaded
    assert guided.button_guide.image_path.name=='button_region.png'
    assert guided.button_guide.parent() is guided.speedometer.parent()
    assert guided.button_guide.parent().parent() is guided.speed_panel
    assert guided.map.parent() is not guided.speed_panel
    plain.close();guided.close()


def test_button_guide_handles_missing_replacement(app,tmp_path):
    guide=ButtonGuideImage(tmp_path/'button_region.png')
    assert not guide.image_loaded
    assert 'IMAGE UNAVAILABLE' in guide.text()
    guide.close()


def test_wan_builder_uses_exact_paths_without_network(app,monkeypatch):
    credentials=WanCredentials('example.invalid',username='test',password='test',
        passphrases={role:'test-passphrase' for role in CameraId},subscriber_token='test-token')
    monkeypatch.setattr('visualization.gui.main.load_wan_credentials',lambda _:credentials)
    monkeypatch.setattr('visualization.gui.sources.wan_video_source.select_srt_decoder',lambda _: '/usr/bin/ffmpeg')
    window=build_two_camera_wan_console('unused')
    assert window.sources.video.camera_ids()==(CameraId.FRONT,CameraId.CABIN)
    for role in window.sources.video.camera_ids():
        assert 'streamid=read:'+role.value+':' in credentials.reader_uri(role)
    window.close()


def test_existing_map_contract_and_launch_modes_preserved():
    script=Path('visualization/gui/assets/navigation.js').read_text()
    assert 'styles/positron' in script and 'marker:"triangle"' in script
    assert 'window.recenter' in script and 'map.easeTo' in script
    main=Path('visualization/gui/main.py').read_text()
    for mode in ('--minimal-wan','--minimal-demo','--wan','--two-camera-wan','--two-camera-demo'):
        assert mode in main
    assert '--button' in main
