"""Camera acquisition and JPEG encoding in its own bounded pipeline."""

from __future__ import annotations

import threading
import time

import cv2

from visualization.common.bounded_queue import DropOldestQueue, QueueClosed
from visualization.common.models import EncodedFrame, FrameMetadata, ProviderStatus
from visualization.onboard.providers.base_camera import CameraProvider, ProviderFailure


class VideoPipeline:
    def __init__(self, provider: CameraProvider, queue_size: int = 3, jpeg_quality: int = 80) -> None:
        self.provider = provider
        self.queue: DropOldestQueue[EncodedFrame] = DropOldestQueue(queue_size)
        self.jpeg_quality = jpeg_quality
        self.latest_metadata: FrameMetadata | None = None
        self.error: str | None = None
        self._started_at = 0.0
        self._stopped_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.provider.start()
        self._started_at = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="viz-video-acquisition", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                frame = self.provider.get_frame()
                ok, encoded = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                if not ok:
                    raise ProviderFailure("JPEG encoding failed")
                self.latest_metadata = frame.metadata
                self.queue.put(EncodedFrame(frame.metadata, encoded.tobytes()))
        except (ProviderFailure, QueueClosed) as exc:
            if not self._stop.is_set():
                self.error = str(exc)
        except Exception as exc:  # isolate unexpected camera/codec failures
            self.error = f"unexpected video failure: {exc}"
        finally:
            self._stopped_at = time.monotonic()
            self.provider.stop()

    def stop(self) -> None:
        self._stop.set()
        self.queue.close()
        if self._thread:
            self._thread.join(timeout=3.0)
        self.provider.stop()

    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def provider_status(self) -> ProviderStatus:
        status = self.provider.status()
        if self.error:
            return ProviderStatus("failed", self.error)
        return status

    def produced_rate_hz(self) -> float:
        if not self._started_at:
            return 0.0
        end = self._stopped_at or time.monotonic()
        duration = max(1e-9, end - self._started_at)
        return self.queue.stats().produced / duration
