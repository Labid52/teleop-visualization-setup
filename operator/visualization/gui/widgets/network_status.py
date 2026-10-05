"""Future-ready network/stream metric presentation without fabricated data."""

from __future__ import annotations

from visualization.gui.models.ui_state import NetworkState
from visualization.gui.widgets.common import PanelFrame, StateBadge, value_row


class NetworkStatusPanel(PanelFrame):
    def __init__(self, parent=None) -> None:
        super().__init__("STREAM HEALTH", "VISUALIZATION NETWORK", parent)
        self.badge = StateBadge("MOCK")
        self.outer.itemAt(0).layout().addWidget(self.badge)
        self.values = {}
        for key, label in (("video", "Video FPS"), ("telemetry", "Telemetry"), ("video_age", "Video freshness"), ("gps_age", "GPS freshness"), ("drops", "Dropped frames"), ("resolution", "Resolution"), ("bitrate", "Bitrate"), ("rtt", "RTT"), ("loss", "Packet loss")):
            row, value = value_row(label)
            self.values[key] = value
            self.outer.addWidget(row)

    def update_network(self, state: NetworkState) -> None:
        self.badge.set_state(state.state.value)
        self.values["video"].setText("--" if state.video_fps is None else f"{state.video_fps:.1f} FPS")
        self.values["telemetry"].setText(f"{state.telemetry_hz:.1f} Hz")
        self.values["video_age"].setText("--" if state.video_freshness_s is None else f"{state.video_freshness_s * 1000:.0f} ms")
        self.values["gps_age"].setText("--" if state.gps_freshness_s is None else f"{state.gps_freshness_s * 1000:.0f} ms")
        self.values["drops"].setText("--" if state.dropped_frames is None else str(state.dropped_frames))
        self.values["resolution"].setText(state.resolution)
        self.values["bitrate"].setText("--" if state.bitrate_kbps is None else f"{state.bitrate_kbps:.0f} kbps")
        self.values["rtt"].setText("--" if state.rtt_ms is None else f"{state.rtt_ms:.1f} ms")
        self.values["loss"].setText("--" if state.packet_loss_percent is None else f"{state.packet_loss_percent:.2f}%")
