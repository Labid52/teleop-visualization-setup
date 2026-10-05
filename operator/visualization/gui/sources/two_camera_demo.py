"""Independent 640x480, 10 FPS fixtures for FRONT and CABIN."""

from visualization.gui.models.ui_state import CameraId
from visualization.gui.sources.console_demo import ConsoleDemoVideo
from visualization.gui.sources.mock_video_source import MockVideoSource


class TwoCameraDemoVideo(MockVideoSource):
    def __init__(self):
        super().__init__(width=640, height=480,
                         fps={CameraId.FRONT: 10, CameraId.CABIN: 10},
                         enabled={CameraId.FRONT, CameraId.CABIN})

    @staticmethod
    def _style(camera_id, sequence, image):
        if camera_id is CameraId.CABIN:
            ConsoleDemoVideo._style(camera_id, sequence, image)
        else:
            MockVideoSource._style(camera_id, sequence, image)
