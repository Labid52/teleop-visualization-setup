"""Qt worker threads keep all acquisition outside the GUI thread."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from visualization.gui.models.ui_state import CameraId, DisplayState
from visualization.gui.sources.base import OperatorStateSource, TelemetrySource, VideoSource


class CameraWorker(QObject):
    frame_ready = Signal(object)
    status_changed = Signal(object, object, str)
    finished = Signal()

    def __init__(self, source: VideoSource, camera_id: CameraId) -> None:
        super().__init__()
        self.source = source
        self.camera_id = camera_id
        self._stop = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            self.source.start_camera(self.camera_id)
            last_status = None
            while not self._stop.is_set():
                frame = self.source.next_frame(self.camera_id)
                status, detail = self.source.camera_status(self.camera_id)
                if status != last_status:
                    self.status_changed.emit(self.camera_id, status, detail)
                    last_status = status
                if frame is not None and not self._stop.is_set():
                    self.frame_ready.emit(frame)
        except Exception:
            self.status_changed.emit(self.camera_id, DisplayState.OFFLINE, "camera source unavailable")
        finally:
            self.source.stop_camera(self.camera_id)
            self.finished.emit()

    def stop(self) -> None:
        self._stop.set()
        self.source.stop_camera(self.camera_id)


class TelemetryWorker(QObject):
    telemetry_ready = Signal(object)
    status_changed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, source: TelemetrySource) -> None:
        super().__init__()
        self.source = source
        self._stop = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            self.source.start()
            last_status = None
            while not self._stop.is_set():
                state = self.source.get_latest()
                status = self.source.status()
                if status != last_status:
                    self.status_changed.emit(status)
                    last_status = status
                if state is not None and not self._stop.is_set():
                    self.telemetry_ready.emit(state)
        except Exception:
            self.failed.emit("telemetry source unavailable")
        finally:
            self.source.stop()
            self.finished.emit()

    def stop(self) -> None:
        self._stop.set()
        self.source.stop()


class OperatorWorker(QObject):
    operator_ready = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, source: OperatorStateSource) -> None:
        super().__init__()
        self.source = source
        self._stop = threading.Event()

    @Slot()
    def run(self) -> None:
        try:
            self.source.start()
            while not self._stop.is_set():
                state = self.source.get_latest()
                if state is not None:
                    self.operator_ready.emit(state)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.source.stop()
            self.finished.emit()

    def stop(self) -> None:
        self._stop.set()


class GuiSourceController(QObject):
    frame_ready = Signal(object)
    camera_status = Signal(object, object, str)
    telemetry_ready = Signal(object)
    telemetry_failed = Signal(str)
    telemetry_status = Signal(object)
    operator_ready = Signal(object)
    operator_failed = Signal(str)

    def __init__(self, video: VideoSource, telemetry: TelemetrySource, operator: OperatorStateSource) -> None:
        super().__init__()
        self.video = video
        self.telemetry = telemetry
        self.operator = operator
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._latest_frames: dict[CameraId, object] = {}
        self._latest_telemetry = None
        self._replaced_frames: dict[CameraId, int] = {camera_id: 0 for camera_id in CameraId}
        self._frame_lock = threading.Lock()
        self._delivery_timer = QTimer(self)
        self._delivery_timer.setInterval(16)
        self._delivery_timer.timeout.connect(self._deliver_latest_frames)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        for camera_id in self.video.camera_ids():
            worker = CameraWorker(self.video, camera_id)
            worker.frame_ready.connect(self._store_latest_frame, Qt.ConnectionType.DirectConnection)
            worker.status_changed.connect(self.camera_status)
            self._start_worker(worker)
        telemetry_worker = TelemetryWorker(self.telemetry)
        telemetry_worker.telemetry_ready.connect(self._store_latest_telemetry, Qt.ConnectionType.DirectConnection)
        telemetry_worker.status_changed.connect(self.telemetry_status)
        telemetry_worker.failed.connect(self.telemetry_failed)
        self._start_worker(telemetry_worker)
        operator_worker = OperatorWorker(self.operator)
        operator_worker.operator_ready.connect(self.operator_ready)
        operator_worker.failed.connect(self.operator_failed)
        self._start_worker(operator_worker)
        self._delivery_timer.start()
        self._started = True

    @Slot(object)
    def _store_latest_frame(self, frame: object) -> None:
        camera_id = frame.camera_id
        with self._frame_lock:
            if camera_id in self._latest_frames:
                self._replaced_frames[camera_id] += 1
            self._latest_frames[camera_id] = frame

    @Slot()
    def _deliver_latest_frames(self) -> None:
        with self._frame_lock:
            frames = tuple(self._latest_frames.values())
            self._latest_frames.clear()
            telemetry, self._latest_telemetry = self._latest_telemetry, None
        for frame in frames:
            self.frame_ready.emit(frame)
        if telemetry is not None:
            self.telemetry_ready.emit(telemetry)

    @Slot(object)
    def _store_latest_telemetry(self, telemetry):
        with self._frame_lock:
            self._latest_telemetry = telemetry

    def _start_worker(self, worker: QObject) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        self._workers.append(worker)
        self._threads.append(thread)
        thread.start()

    def stop(self) -> None:
        self._delivery_timer.stop()
        for worker in self._workers:
            worker.stop()
        for thread in self._threads:
            thread.quit()
        for thread in self._threads:
            thread.wait(7000)
        remaining = [(thread, worker) for thread, worker in zip(self._threads, self._workers) if thread.isRunning()]
        self._threads = [thread for thread, _worker in remaining]
        self._workers = [worker for _thread, worker in remaining]
        self._started = bool(remaining)

    def threads_running(self) -> int:
        return sum(thread.isRunning() for thread in self._threads)

    def dropped_before_render(self, camera_id: CameraId) -> int:
        with self._frame_lock:
            return self._replaced_frames[camera_id]
