from __future__ import annotations

import pytest

from visualization.onboard.providers.base_camera import ProviderFailure
from visualization.onboard.providers.mock_camera import MockCameraProvider
from visualization.onboard.providers.mock_gps import MockGPSProvider


def test_mock_camera_advances_and_draws_frames() -> None:
    camera = MockCameraProvider(width=160, height=90, target_fps=100.0)
    camera.start()
    first = camera.get_frame()
    second = camera.get_frame()
    camera.stop()
    assert [first.metadata.frame_sequence, second.metadata.frame_sequence] == [0, 1]
    assert first.image.shape == (90, 160, 3)
    assert first.metadata.capture_time_monotonic_s < second.metadata.capture_time_monotonic_s


def test_mock_camera_can_simulate_failure() -> None:
    camera = MockCameraProvider(target_fps=100.0, fail_after_frames=1)
    camera.start()
    camera.get_frame()
    with pytest.raises(ProviderFailure):
        camera.get_frame()
    assert camera.status().state == "failed"


def test_mock_gps_trajectory_is_deterministic_and_advances() -> None:
    gps = MockGPSProvider(target_hz=100.0)
    gps.start()
    first = gps.get_latest()
    second = gps.get_latest()
    gps.stop()
    assert [first.sequence, second.sequence] == [0, 1]
    assert second.latitude > first.latitude
    assert second.longitude > first.longitude
    assert second.fix_valid


def test_mock_gps_can_simulate_failure() -> None:
    gps = MockGPSProvider(target_hz=100.0, fail_after_updates=1)
    gps.start()
    gps.get_latest()
    with pytest.raises(ProviderFailure):
        gps.get_latest()
    assert gps.status().state == "failed"
