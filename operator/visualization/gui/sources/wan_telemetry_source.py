"""Authenticated, latest-state visualization subscriber; no control integration."""

from collections import deque
from datetime import datetime
import json
import logging
import math
import socket
import threading
import time

from websockets.sync.client import connect

from visualization.gui.models.ui_state import (
    CameraHealthState, CameraId, DisplayState, GPSState, HealthState,
    NetworkState, TelemetryState,
)
from visualization.gui.sources.base import TelemetrySource


def subscriber_auth(token: str) -> str:
    return json.dumps({"type": "auth", "role": "subscriber", "token": token})


def validate_message(raw: str | bytes) -> dict:
    if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > 65536:
        raise ValueError("message too large")
    def reject_constant(_value):
        raise ValueError("non-finite JSON")
    message = json.loads(raw, parse_constant=reject_constant)
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite number")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)
    finite(message)
    if not isinstance(message, dict) or type(message.get("schema_version")) is not int or message["schema_version"] != 1 or message.get("message_type") != "vehicle_visualization":
        raise ValueError("unsupported visualization schema")
    return message


def number(value):
    if type(value) not in (int, float):
        return None
    try:
        return float(value) if math.isfinite(value) else None
    except OverflowError:
        return None


def object_field(message, key):
    value = message.get(key)
    return value if isinstance(value, dict) else {}


def map_telemetry(message: dict, received: float, rate: float) -> TelemetryState:
    gnss = object_field(message, "gnss")
    system = object_field(message, "system")
    cameras = object_field(message, "cameras")
    camera_states = {}
    for role in CameraId:
        camera = object_field(cameras, role.value)
        if camera:
            camera_states[role] = CameraHealthState(
                camera.get("healthy") if type(camera.get("healthy")) is bool else None,
                number(camera.get("fps")), number(camera.get("last_frame_age_s")),
                camera.get("stream_path", "") if isinstance(camera.get("stream_path", ""), str) else "",
            )
    latitude = number(gnss.get("latitude_deg"))
    longitude = number(gnss.get("longitude_deg"))
    latitude = latitude if latitude is not None and -90 <= latitude <= 90 else None
    longitude = longitude if longitude is not None and -180 <= longitude <= 180 else None
    fix = gnss.get("fix_valid") is True
    heading = number(gnss.get("heading_deg"))
    heading = heading if heading is not None and 0 <= heading < 360 else None
    heading_source = gnss.get("heading_source", "UNAVAILABLE")
    if not isinstance(heading_source, str) or heading is None:
        heading_source = "UNAVAILABLE"
    gps_age = None
    try:
        gps_age = max(0.0, (datetime.fromisoformat(message["timestamp_utc"].replace("Z", "+00:00")) - datetime.fromisoformat(gnss["timestamp_utc"].replace("Z", "+00:00"))).total_seconds())
    except (KeyError, TypeError, ValueError):
        pass
    gps_state = DisplayState.LIVE if fix and latitude is not None and longitude is not None else DisplayState.NO_DATA
    if gps_age is not None and gps_age > 2.5:
        gps_state = DisplayState.STALE
    sequence = message.get("sequence")
    sequence = sequence if type(sequence) is int and sequence >= 0 else None
    gps = GPSState(sequence if sequence is not None else 0, str(gnss.get("timestamp_utc", "")), received - (gps_age or 0), latitude, longitude, number(gnss.get("horizontal_speed_mps")), heading, fix,
                   gnss.get("satellite_count") if type(gnss.get("satellite_count")) is int else None,
                   number(gnss.get("horizontal_accuracy_m")), gps_state, heading_source, bool(gnss))
    front = camera_states.get(CameraId.FRONT)
    video_state = DisplayState.LIVE if front and front.healthy is True else DisplayState.NO_DATA
    health = HealthState(number(system.get("cpu_percent")), number(system.get("memory_percent")), None, number(system.get("uptime_s")), video_state,
                         number(system.get("telemetry_rate_hz")), front.fps if front else None, None,
                         DisplayState.LIVE if system else DisplayState.NO_DATA, number(system.get("temperature_c")))
    network = NetworkState(front.fps if front else None, rate, front.frame_age_s if front else None, gps_age, None, "--", state=DisplayState.LIVE)
    return TelemetryState(gps, health, network, sequence, str(message.get("timestamp_utc", "")), received, DisplayState.LIVE, camera_states)


class WanTelemetrySource(TelemetrySource):
    mode = "WAN"

    def __init__(self, credentials, stale_after_s=2.5, connector=connect):
        self.credentials = credentials
        self.stale_after_s = stale_after_s
        self.connector = connector
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._connection = None
        self._state = DisplayState.CONNECTING
        self._next_attempt = 0.0
        self._backoff = 1.0
        self._last_progress = 0.0
        self._progress_key = None
        self._latest = None
        self._times = deque(maxlen=120)
        self.messages = self.malformed = self.repeats = self.disconnects = self.reconnects = self.authentications = 0
        self.sequence_regressions = self.timestamp_regressions = 0
        self.first_sequence = None
        self.first_timestamp_utc = None
        self._logger = logging.Logger("visualization-subscriber", level=logging.CRITICAL + 1)
        self._logger.addHandler(logging.NullHandler())

    def start(self):
        pass

    def _retry(self):
        with self._lock:
            ws, self._connection = self._connection, None
            if ws is not None:
                self.disconnects += 1
            self._state = DisplayState.DISCONNECTED
            self._next_attempt = time.monotonic() + self._backoff
            self._backoff = min(15.0, self._backoff * 2)
        if ws is not None:
            ws.close()

    def _connect(self):
        self._state = DisplayState.CONNECTING
        ws = self.connector(self.credentials.telemetry_uri, open_timeout=3, close_timeout=.5, ping_interval=5, ping_timeout=5,
                            max_size=65536, max_queue=(1, 0), compression=None, proxy=None, logger=self._logger)
        with self._lock:
            if self._stop.is_set():
                ws.close()
                return
            self._connection = ws
        # Bound detection of an orphaned TCP session after a local network change.
        if hasattr(ws, "socket"):
            ws.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            for option, value in (("TCP_KEEPIDLE", 5), ("TCP_KEEPINTVL", 3), ("TCP_KEEPCNT", 3)):
                if hasattr(socket, option):
                    ws.socket.setsockopt(socket.IPPROTO_TCP, getattr(socket, option), value)
        ws.send(subscriber_auth(self.credentials.subscriber_token))
        ack = json.loads(ws.recv(timeout=3))
        if ack != {"type": "auth_ok", "role": "subscriber"}:
            raise ValueError("subscriber authentication rejected")
        self.reconnects += bool(self.authentications)
        self.authentications += 1
        self._state = DisplayState.NO_DATA
        self._progress_key = None
        self._last_progress = 0

    def get_latest(self):
        if self._stop.is_set():
            return None
        if self._connection is None:
            if time.monotonic() < self._next_attempt:
                self._stop.wait(.1)
                return None
            try:
                self._connect()
            except Exception:
                self._retry()
                return None
        ws = self._connection
        if ws is None:
            return None
        try:
            raw = ws.recv(timeout=.1)
        except TimeoutError:
            return None
        except Exception:
            if not self._stop.is_set():
                self._retry()
            return None
        try:
            message = validate_message(raw)
            # Do not relabel a repeatedly served cached state as fresh.
            key = (message.get("sequence"), message.get("timestamp_utc"), message.get("timestamp_monotonic_s"))
            if key == self._progress_key and key != (None, None, None):
                self.repeats += 1
                return None
            if self._progress_key is not None:
                previous_sequence, previous_utc, previous_monotonic = self._progress_key
                if type(key[0]) is int and type(previous_sequence) is int and key[0] <= previous_sequence:
                    self.sequence_regressions += 1
                if number(key[2]) is not None and number(previous_monotonic) is not None and key[2] <= previous_monotonic:
                    self.timestamp_regressions += 1
            now = time.monotonic()
            self._times.append(now)
            rate = (len(self._times) - 1) / max(.001, self._times[-1] - self._times[0])
            state = map_telemetry(message, now, rate)
            previous_key = self._progress_key
            self._progress_key = key
            self._last_progress = now
            self._latest = state
            self.messages += 1
            if self.first_sequence is None:
                self.first_sequence = state.sequence
                self.first_timestamp_utc = state.timestamp_utc
            self._state = DisplayState.LIVE if previous_key is not None else DisplayState.NO_DATA
            self._backoff = 1
            # A newly connected subscriber may receive only the server's cache.
            # Require subsequent progress before displaying it as live data.
            return state if previous_key is not None else None
        except (ValueError, TypeError, RecursionError):
            self.malformed += 1
            return None

    def status(self):
        if self._stop.is_set():
            return DisplayState.DISCONNECTED
        if self._state is DisplayState.LIVE and time.monotonic() - self._last_progress > self.stale_after_s:
            return DisplayState.STALE
        return self._state

    def stop(self):
        self._stop.set()
        with self._lock:
            ws, self._connection = self._connection, None
        if ws is not None:
            ws.close()

    def diagnostics(self):
        latest = self._latest
        return {"state": self.status().value, "authenticated": self.authentications > 0, "messages": self.messages, "malformed": self.malformed,
                "cached_repeats": self.repeats, "disconnects": self.disconnects, "reconnects": self.reconnects,
                "last_sequence": latest.sequence if latest else None,
                "first_sequence": self.first_sequence,
                "first_timestamp_utc": self.first_timestamp_utc,
                "sequence_regressions": self.sequence_regressions,
                "timestamp_regressions": self.timestamp_regressions,
                "last_timestamp_utc": latest.timestamp_utc if latest else None,
                "receive_hz": latest.network.telemetry_hz if latest else 0,
                "gnss_fix": latest.gps.fix_valid if latest else None,
                "heading_source": latest.gps.heading_source if latest else None,
                "cameras": [role.value for role in latest.cameras] if latest else [],
                "system_present": bool(latest and latest.health.state is DisplayState.LIVE)}
