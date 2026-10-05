"""Optional, replaceable G29 button-region guide."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


DEFAULT_BUTTON_GUIDE_PATH = Path(__file__).resolve().parents[3] / "button_region.png"


class ButtonGuideImage(QLabel):
    """Aspect-fit an external guide image without making it a launch dependency."""

    def __init__(self, image_path: Path = DEFAULT_BUTTON_GUIDE_PATH, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.source_pixmap = QPixmap(str(self.image_path))
        self.image_loaded = not self.source_pixmap.isNull()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 130)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #090f16; border: 1px solid #263d53; border-radius: 8px; color: #90abc3;")
        if self.image_loaded:
            self._fit_pixmap()
        else:
            self.setText("G29 BUTTON GUIDE\nIMAGE UNAVAILABLE")

    def _fit_pixmap(self):
        if self.image_loaded and self.width() > 0 and self.height() > 0:
            self.setPixmap(self.source_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_pixmap()
