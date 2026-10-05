"""Consistent UTC wall-clock and monotonic timestamp capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time


@dataclass(frozen=True)
class TimestampPair:
    utc: str
    monotonic_s: float


def now() -> TimestampPair:
    """Capture both clocks close together for one record."""
    monotonic = time.monotonic()
    utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return TimestampPair(utc=utc, monotonic_s=monotonic)
