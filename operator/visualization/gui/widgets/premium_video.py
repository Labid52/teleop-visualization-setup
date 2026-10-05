"""4:3 cabin viewport and stable controls, specific to the compact console."""

from collections import deque
import time

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class StatusPill(QLabel):
    def __init__(self, state="NO DATA", width=112, parent=None):
        super().__init__(parent)
        self.setObjectName("pill")
        self.setFixedSize(width, 28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(state)

    def set_state(self, state):
        if self.text() == state:
            return
        self.setText(state)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


def caption(text, name="caption"):
    label = QLabel(text)
    label.setObjectName(name)
    return label


def button(text, width=68):
    result = QPushButton(text)
    result.setFixedSize(width, 28)
    return result


class VideoViewport(QWidget):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.image = None
        self.message = "CONNECTING"
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def image_rect(self):
        if self.image is None:
            return QRectF(self.rect())
        size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        return QRectF((self.width()-size.width())/2, (self.height()-size.height())/2, size.width(), size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#080e17"))
        if self.image is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawImage(self.image_rect(), self.image)
        else:
            painter.setPen(QColor("#728ba3"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)

    def mouseDoubleClickEvent(self, event):
        self.activated.emit()


class CabinVideoCard(QFrame):
    activated = Signal()
    CHROME_HEIGHT = 68

    def __init__(self, title="01  /  CABIN"):
        super().__init__()
        self.setObjectName("premiumCard")
        self._stream_state = "CONNECTING"
        self.last_frame_time = None
        self.rendered_frames = 0
        self._times = deque(maxlen=60)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(0)
        header = QWidget()
        header.setFixedHeight(42)
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 0, 10, 0)
        row.addWidget(caption(title, "sectionTitle"))
        row.addStretch()
        self.state_badge = StatusPill("CONNECTING")
        row.addWidget(self.state_badge)
        self.maximize_button = button("MAX", 52)
        self.maximize_button.clicked.connect(self.activated)
        row.addWidget(self.maximize_button)
        layout.addWidget(header)
        self.image_label = VideoViewport()
        self.image_label.activated.connect(self.activated)
        layout.addWidget(self.image_label)
        self.footer = caption("WAITING FOR VIDEO", "muted")
        self.footer.setFixedHeight(26)
        self.footer.setContentsMargins(14, 0, 0, 0)
        layout.addWidget(self.footer)

    def height_for_width(self, width):
        return round((width - 2) * 3 / 4) + self.CHROME_HEIGHT

    def update_frame(self, frame):
        image = frame.image_bgr
        if not image.flags.c_contiguous:
            image = image.copy()
        height, width, _ = image.shape
        self.image_label.image = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_BGR888).copy()
        self.last_frame_time = frame.capture_time_monotonic_s
        self.rendered_frames += 1
        self._times.append(time.monotonic())
        self.set_stream_state("LIVE")
        self.footer.setText(f"{width} × {height}    /    {self.rendered_fps():.1f} FPS")
        self.image_label.update()

    def set_stream_state(self, state):
        state = getattr(state, "value", state)
        state = {"MOCK": "LIVE", "WAITING": "RECONNECTING", "DISCONNECTED": "RECONNECTING", "OFFLINE": "NO DATA"}.get(state, state)
        if state == "LIVE" and self.image_label.image is None:
            state = "CONNECTING"
        self._stream_state = state
        self.state_badge.set_state(state)
        if state != "LIVE":
            self.image_label.image = None
            self.image_label.message = "NO FRESH VIDEO" if state == "STALE" else state
            self.image_label.update()

    def refresh_metrics(self):
        if self.last_frame_time is not None and time.monotonic() - self.last_frame_time > 2.5:
            if self._stream_state == "LIVE":
                self.set_stream_state("STALE")

    def rendered_fps(self):
        return (len(self._times)-1) / max(.001, self._times[-1]-self._times[0]) if len(self._times)>1 else 0.0
