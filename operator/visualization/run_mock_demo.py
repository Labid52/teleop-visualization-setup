"""Sustained localhost demonstration with measurable Level 3A evidence."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import time

import psutil

from visualization.onboard.config import load_config
from visualization.onboard.main import VisualizationAgent
from visualization.receiver.diagnostic_receiver import DiagnosticReceiver


def run(duration_s: float, reconnect_pause_s: float = 1.0) -> dict[str, object]:
    config = load_config("visualization/config/visualization.example.yaml")
    config = replace(config, telemetry=replace(config.telemetry, local_port=0), video=replace(config.video, local_port=0))
    agent = VisualizationAgent(config)
    process = psutil.Process()
    rss_samples: list[int] = []
    total_frames = 0
    total_decoded = 0
    total_telemetry = 0
    receiver_errors: list[str] = []
    reconnected = False
    receiver: DiagnosticReceiver | None = None
    started = time.monotonic()
    next_memory_sample = started
    reconnect_at = started + duration_s / 3.0
    agent.start()
    try:
        receiver = DiagnosticReceiver(telemetry_port=agent.telemetry_server.port, video_port=agent.video_server.port)
        receiver.start()
        while time.monotonic() - started < duration_s:
            current = time.monotonic()
            if current >= next_memory_sample:
                rss_samples.append(process.memory_info().rss)
                next_memory_sample = current + 1.0
            if not reconnected and current >= reconnect_at:
                receiver.stop()
                total_frames += receiver.frames_received
                total_decoded += receiver.frames_decoded
                total_telemetry += receiver.telemetry_received
                receiver_errors.extend(receiver.errors)
                time.sleep(reconnect_pause_s)
                receiver = DiagnosticReceiver(telemetry_port=agent.telemetry_server.port, video_port=agent.video_server.port)
                receiver.start()
                reconnected = True
            time.sleep(0.05)
    finally:
        if receiver is not None:
            receiver.stop()
            total_frames += receiver.frames_received
            total_decoded += receiver.frames_decoded
            total_telemetry += receiver.telemetry_received
            receiver_errors.extend(receiver.errors)
        agent.stop()
    elapsed = time.monotonic() - started
    video_stats = agent.video.queue.stats()
    telemetry_stats = agent.telemetry.queue.stats()
    latest_gps = agent.telemetry.latest_gps
    return {
        "duration_s": elapsed,
        "video_frames_produced": video_stats.produced,
        "video_frames_sent": agent.video_server.frames_sent,
        "video_frames_received": total_frames,
        "video_frames_decoded": total_decoded,
        "video_frames_dropped_locally": video_stats.dropped_oldest,
        "video_rate_produced_hz": video_stats.produced / elapsed,
        "video_rate_received_hz": total_frames / elapsed,
        "telemetry_messages_produced": telemetry_stats.produced,
        "telemetry_messages_sent": agent.telemetry_server.messages_sent,
        "telemetry_messages_received": total_telemetry,
        "telemetry_rate_produced_hz": telemetry_stats.produced / elapsed,
        "telemetry_rate_received_hz": total_telemetry / elapsed,
        "gps_updates": None if latest_gps is None else latest_gps.sequence + 1,
        "gps_update_rate_hz": None if latest_gps is None else (latest_gps.sequence + 1) / elapsed,
        "video_maximum_queue_depth": video_stats.maximum_observed_depth,
        "telemetry_maximum_queue_depth": telemetry_stats.maximum_observed_depth,
        "rss_start_bytes": rss_samples[0] if rss_samples else None,
        "rss_end_bytes": rss_samples[-1] if rss_samples else None,
        "rss_min_bytes": min(rss_samples) if rss_samples else None,
        "rss_max_bytes": max(rss_samples) if rss_samples else None,
        "rss_growth_bytes": (rss_samples[-1] - rss_samples[0]) if len(rss_samples) > 1 else None,
        "receiver_reconnected": reconnected and agent.telemetry_server.connections >= 2 and agent.video_server.connections >= 2,
        "telemetry_connections": agent.telemetry_server.connections,
        "video_connections": agent.video_server.connections,
        "camera_error": agent.video.error,
        "telemetry_error": agent.telemetry.error,
        "receiver_errors": receiver_errors,
        "clean_shutdown": agent.all_threads_stopped(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a localhost mock visualization demonstration")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--output", help="optional JSON evidence file")
    args = parser.parse_args()
    result = run(args.duration)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
