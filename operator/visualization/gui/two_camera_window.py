"""FRONT + CABIN extension of the approved cabin/GNSS console."""

from PySide6.QtWidgets import QHBoxLayout, QWidget

from visualization.gui.minimal_window import ConsoleBody, MinimalOperatorConsole
from visualization.gui.models.ui_state import CameraId
from visualization.gui.widgets.button_guide import ButtonGuideImage
from visualization.gui.widgets.premium_video import CabinVideoCard


class TwoCameraBody(ConsoleBody):
    def __init__(self, left, right, row, tiles, speed):
        super().__init__(left, right, tiles[CameraId.CABIN], speed)
        self.row = row
        self.tiles = tiles
        self.focus_role = None

    def arrange(self):
        super().arrange()
        width = self.left.width()
        if not self.focus:
            # Start from the previous proportions, then target 30% less speed
            # panel height. Aspect-correct camera growth requires more width;
            # retain enough room for readable map controls and GNSS metrics.
            width = min(round(width * 1.12), round(self.width() * .54))
            previous_camera_height = round((((width - 14) // 2) - 4) * 3 / 4) + 70
            previous_speed_height = self.height() - previous_camera_height - 14
            camera_height = self.height() - round(previous_speed_height * .70) - 14
            desired_width = 2 * (round((camera_height - 70) * 4 / 3) + 4) + 14
            right_minimum = max(480, self.right.minimumSizeHint().width())
            width = min(desired_width, self.width() - right_minimum - 14)
            self.left.setFixedWidth(width)
        if self.focus:
            tile = self.tiles[self.focus_role]
            height = round((width - 4) * 3 / 4) + 70
            tile.setFixedHeight(height)
        else:
            tile_width = (width - 14) // 2
            # Account for the existing card's border plus content margins:
            # viewport width is card width minus four; chrome is 70 pixels.
            height = round((tile_width - 4) * 3 / 4) + 70
            for tile in self.tiles.values():
                tile.setFixedHeight(height)
        self.row.setFixedHeight(height)


class TwoCameraOperatorConsole(MinimalOperatorConsole):
    def __init__(self, sources, map_factory=None, show_button=False):
        super().__init__(sources, map_factory)
        # Two complete headers need enough room for the approved fixed badges.
        # The original one-camera window's minimum size remains unchanged.
        self.setMinimumSize(1360, 860)
        self.front = CabinVideoCard("01  /  FRONT")
        self.tiles = {CameraId.FRONT: self.front, CameraId.CABIN: self.cabin}
        self.button_guide = None
        if show_button:
            self._add_button_guide()
        old_body = self.body
        left_layout = old_body.left.layout()
        left_layout.removeWidget(self.cabin)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(14)
        row_layout.addWidget(self.front, 1)
        row_layout.addWidget(self.cabin, 1)
        left_layout.insertWidget(0, row)
        self.body = TwoCameraBody(old_body.left, old_body.right, row, self.tiles, self.speed_panel)
        self.centralWidget().layout().replaceWidget(old_body, self.body)
        old_body.hide()
        old_body.deleteLater()
        self.front.activated.connect(lambda: self.toggle_camera_focus(CameraId.FRONT))

    def _add_button_guide(self):
        """Split only the speedometer content row; camera/GNSS/map stay intact."""
        speed_layout = self.speed_panel.layout()
        instrument_row = QWidget()
        instrument_layout = QHBoxLayout(instrument_row)
        instrument_layout.setContentsMargins(0, 0, 0, 0)
        instrument_layout.setSpacing(14)
        speed_layout.replaceWidget(self.speedometer, instrument_row)
        self.speedometer.setParent(instrument_row)
        instrument_layout.addWidget(self.speedometer, 1)
        self.button_guide = ButtonGuideImage()
        instrument_layout.addWidget(self.button_guide, 1)

    def on_frame(self, frame):
        tile = self.tiles.get(frame.camera_id)
        if tile is not None:
            tile.update_frame(frame)

    def on_camera_status(self, camera_id, state, detail):
        tile = self.tiles.get(camera_id)
        if tile is not None:
            tile.set_stream_state(state)
            if tile._stream_state == "NO DATA":
                tile.set_stream_state("NO VIDEO")

    def refresh(self):
        super().refresh()
        self.front.refresh_metrics()
        states = [tile._stream_state for tile in self.tiles.values()]
        # Per-tile badges remain authoritative; the existing compact strip
        # indicates whether both video links are live.
        video = "LIVE" if all(state == "LIVE" for state in states) else next(state for state in states if state != "LIVE")
        self.video_badge.set_state(video)
        if self.mode == "WAN":
            ready = video == "LIVE" and self.gps.state == "LIVE"
            self.remote_badge.set_state("REMOTE LINK · " + ("LIVE" if ready else "READY"))

    def toggle_camera_focus(self, role=CameraId.CABIN):
        if self.body.focus and self.body.focus_role == role:
            self.body.focus = False
            self.body.focus_role = None
        else:
            self.body.focus = True
            self.body.focus_role = role
        for camera_id, tile in self.tiles.items():
            tile.setVisible(not self.body.focus or camera_id == self.body.focus_role)
            tile.maximize_button.setText("BACK" if self.body.focus and camera_id == role else "MAX")
        self.body.right.setVisible(not self.body.focus)
        self.speed_panel.setVisible(not self.body.focus)
        self.body.arrange()

    def restore_view(self):
        if self.body.focus:
            self.toggle_camera_focus(self.body.focus_role)
        if self.isFullScreen():
            self.toggle_fullscreen()

    def metrics(self):
        result = super().metrics()
        result.update(front_frames_rendered=self.front.rendered_frames,
                      front_fps=self.front.rendered_fps(), front_status=self.front._stream_state)
        return result
