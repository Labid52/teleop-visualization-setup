"""Bounded framing for FFmpeg's local image2pipe BMP output."""

import struct


class BmpFrameBuffer:
    def __init__(self, maximum_bytes: int = 8 * 1024 * 1024) -> None:
        self.maximum_bytes = maximum_bytes
        self._buffer = bytearray()

    def append(self, data: bytes) -> None:
        if len(self._buffer) + len(data) > self.maximum_bytes:
            raise ValueError("decoded frame exceeds local buffer limit")
        self._buffer.extend(data)

    def pop(self) -> bytes | None:
        if len(self._buffer) < 14:
            return None
        if self._buffer[:2] != b"BM":
            raise ValueError("invalid decoder frame header")
        size = struct.unpack_from("<I", self._buffer, 2)[0]
        if size < 54 or size > self.maximum_bytes:
            raise ValueError("invalid or oversized decoder frame")
        if len(self._buffer) < size:
            return None
        frame = bytes(self._buffer[:size])
        del self._buffer[:size]
        return frame

    def __len__(self) -> int:
        return len(self._buffer)
