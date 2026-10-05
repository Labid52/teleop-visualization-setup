from __future__ import annotations

import time
import threading

from visualization.tests.conftest import ephemeral_config, wait_until
from visualization.common.bounded_queue import QueueClosed
from visualization.onboard.main import VisualizationAgent
from visualization.onboard.pipeline.video_pipeline import VideoPipeline
from visualization.onboard.providers.mock_camera import MockCameraProvider
from visualization.onboard.providers.mock_gps import MockGPSProvider
from visualization.receiver.diagnostic_receiver import DiagnosticReceiver


def make_receiver(agent: VisualizationAgent, delay: float = 0.0) -> DiagnosticReceiver:
    return DiagnosticReceiver(telemetry_port=agent.telemetry_server.port, video_port=agent.video_server.port, video_consumer_delay_s=delay)


def test_normal_mock_operation_advances_video_gps_and_telemetry() -> None:
    agent = VisualizationAgent(ephemeral_config())
    agent.start()
    receiver = make_receiver(agent)
    receiver.start()
    try:
        assert wait_until(lambda: receiver.frames_received >= 5 and receiver.telemetry_received >= 5)
        assert receiver.latest_frame_metadata["frame_sequence"] >= 4
        assert receiver.latest_telemetry["gps"]["sequence"] >= 4
        assert receiver.latest_telemetry["schema_version"] == 1
        assert receiver.latest_telemetry["message_type"] == "vehicle_visualization"
    finally:
        receiver.stop()
        agent.stop()
    assert agent.all_threads_stopped()


def test_camera_failure_does_not_stop_gps_or_telemetry() -> None:
    camera = MockCameraProvider(width=160, height=90, target_fps=100.0, fail_after_frames=3)
    agent = VisualizationAgent(ephemeral_config(), camera=camera)
    agent.start()
    receiver = make_receiver(agent)
    receiver.start()
    try:
        assert wait_until(lambda: agent.video.error is not None)
        before = receiver.telemetry_received
        assert wait_until(lambda: receiver.telemetry_received >= before + 4)
        assert receiver.latest_telemetry["gps"]["sequence"] >= 3
        assert receiver.latest_telemetry["camera"]["provider_state"] == "failed"
    finally:
        receiver.stop()
        agent.stop()


def test_gps_failure_does_not_stop_video_or_telemetry() -> None:
    gps = MockGPSProvider(target_hz=100.0, fail_after_updates=2)
    agent = VisualizationAgent(ephemeral_config(), gps=gps)
    agent.start()
    receiver = make_receiver(agent)
    receiver.start()
    try:
        assert wait_until(lambda: agent.telemetry.error is not None)
        frames_before = receiver.frames_received
        telemetry_before = receiver.telemetry_received
        assert wait_until(lambda: receiver.frames_received >= frames_before + 4 and receiver.telemetry_received >= telemetry_before + 4)
        assert receiver.latest_telemetry["gps"] is None
        assert receiver.latest_telemetry["gps_status"] == "failed"
    finally:
        receiver.stop()
        agent.stop()


def test_slow_video_consumer_keeps_latest_frames_and_bounded_memory() -> None:
    camera = MockCameraProvider(width=160, height=90, target_fps=80.0)
    pipeline = VideoPipeline(camera, queue_size=2)
    consumed_sequences: list[int] = []
    stop = threading.Event()

    def slow_consumer() -> None:
        while not stop.is_set():
            try:
                frame = pipeline.queue.get(timeout=0.1)
            except TimeoutError:
                continue
            except QueueClosed:
                return
            consumed_sequences.append(frame.metadata.frame_sequence)
            time.sleep(0.08)

    pipeline.start()
    consumer = threading.Thread(target=slow_consumer)
    consumer.start()
    try:
        assert wait_until(lambda: pipeline.queue.stats().dropped_oldest > 0, timeout=3.0)
        assert wait_until(lambda: len(consumed_sequences) >= 5)
        stats = pipeline.queue.stats()
        assert stats.depth <= 2
        assert stats.maximum_observed_depth <= 2
        assert consumed_sequences[-1] > len(consumed_sequences)
    finally:
        stop.set()
        pipeline.stop()
        consumer.join(1.0)


def test_receiver_disconnect_and_reconnect_does_not_stop_acquisition() -> None:
    agent = VisualizationAgent(ephemeral_config())
    agent.start()
    first = make_receiver(agent)
    first.start()
    try:
        assert wait_until(lambda: first.telemetry_received >= 3 and first.frames_received >= 3)
        produced_before = agent.video.queue.stats().produced
        first.stop()
        assert wait_until(lambda: agent.video.queue.stats().produced >= produced_before + 5)
        second = make_receiver(agent)
        second.start()
        try:
            assert wait_until(lambda: second.telemetry_received >= 3 and second.frames_received >= 3)
        finally:
            second.stop()
    finally:
        first.stop()
        agent.stop()
    assert agent.telemetry_server.connections >= 2
    assert agent.video_server.connections >= 2


def test_graceful_shutdown_releases_threads_and_sockets() -> None:
    config = ephemeral_config()
    agent = VisualizationAgent(config)
    agent.start()
    receiver = make_receiver(agent)
    receiver.start()
    assert wait_until(lambda: receiver.frames_received >= 2)
    receiver.stop()
    agent.stop()
    assert agent.all_threads_stopped()
    assert all(not thread.is_alive() for thread in receiver._threads)
