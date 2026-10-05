from __future__ import annotations

import json
import threading
import time

import pytest

from visualization.common.bounded_queue import DropOldestQueue, QueueClosed
from visualization.common.timestamps import now
from visualization.onboard.config import load_config


def test_drop_oldest_queue_is_bounded_and_reports_statistics() -> None:
    queue = DropOldestQueue[int](2)
    queue.put(1)
    queue.put(2)
    queue.put(3)
    assert queue.get() == 2
    assert queue.get() == 3
    stats = queue.stats()
    assert (stats.produced, stats.consumed, stats.dropped_oldest) == (3, 2, 1)
    assert stats.maximum_observed_depth == 2


def test_closed_queue_unblocks_waiter() -> None:
    queue = DropOldestQueue[int](1)
    observed: list[type[Exception]] = []

    def wait() -> None:
        try:
            queue.get()
        except QueueClosed as exc:
            observed.append(type(exc))

    thread = threading.Thread(target=wait)
    thread.start()
    time.sleep(0.02)
    queue.close()
    thread.join(1.0)
    assert observed == [QueueClosed]


def test_timestamp_contains_utc_and_monotonic_values() -> None:
    stamp = now()
    assert stamp.utc.endswith("Z")
    assert stamp.monotonic_s > 0


def test_example_configuration_is_safe_loopback_mock() -> None:
    config = load_config("visualization/config/visualization.example.yaml")
    assert config.camera.provider == "mock"
    assert config.gps.provider == "mock"
    assert config.telemetry.local_host == "127.0.0.1"
    assert config.video.local_host == "127.0.0.1"
    assert json.dumps(config.__dict__, default=str)


def test_non_loopback_diagnostic_server_is_rejected() -> None:
    from visualization.onboard.transport.local_telemetry_server import LocalTelemetryServer

    with pytest.raises(ValueError):
        LocalTelemetryServer(DropOldestQueue(1), host="0.0.0.0")
