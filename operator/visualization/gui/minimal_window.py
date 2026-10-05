"""Premium cabin/GNSS console. Full dashboard and source transports are separate."""

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import time

import psutil
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from visualization.gui.models.navigation import CourseEstimator
from visualization.gui.models.ui_state import CameraId, DisplayState
from visualization.gui.premium_style import PREMIUM_STYLE
from visualization.gui.widgets.premium_video import CabinVideoCard, StatusPill, button, caption
from visualization.gui.widgets.course_indicator import CourseIndicator
from visualization.gui.widgets.online_map import OnlineMapWidget
from visualization.gui.widgets.speedometer import SpeedometerWidget


def card():
    widget=QFrame();widget.setObjectName("premiumCard")
    layout=QVBoxLayout(widget);layout.setContentsMargins(18,14,18,14);layout.setSpacing(10)
    return widget,layout


class MinimalGpsPanel(QFrame):
    STALE_AFTER=2.5
    EXPIRE_AFTER=30.0

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("premiumCard")
        layout=QVBoxLayout(self);layout.setContentsMargins(20,16,20,16);layout.setSpacing(10)
        header=QHBoxLayout();header.addWidget(caption("02  /  POSITION","sectionTitle"));header.addStretch()
        self.state_badge=StatusPill();header.addWidget(self.state_badge);layout.addLayout(header)
        self.values={}
        for key in ("latitude","longitude"):
            row=QHBoxLayout();row.addWidget(caption(key.upper()));row.addStretch()
            value=caption("—","coordinate");self.values[key]=value;row.addWidget(value)
            layout.addLayout(row)
        # This separately parented metrics block is placed alongside the course rose.
        self.details=QWidget(self)
        grid=QGridLayout(self.details);grid.setContentsMargins(0,0,0,0);grid.setSpacing(8)
        for i,(key,label) in enumerate((("satellites","SATELLITES"),("accuracy","ACCURACY"),("fix","FIX"),("age","UPDATE AGE"))):
            cell=QVBoxLayout();cell.setSpacing(3);cell.addWidget(caption(label))
            value=caption("—","metric" if key in ("satellites","accuracy") else "muted")
            self.values[key]=value;cell.addWidget(value);grid.addLayout(cell,i//2,i%2)
        self.values["speed"]=QLabel("--",self);self.values["speed"].hide()
        self._last_gps=None
        self._last_key=None
        self._last_gps_monotonic=None
        self._missing=False
        self._has_gnss=False
        self.age_s=None
        self.state="NO DATA"

    def update_state(self,gps):
        if not gps.published or not gps.fix_valid or gps.latitude is None or gps.longitude is None:
            self._missing=True
            self.refresh_age()
            if not self._has_gnss:
                self.values["fix"].setText("GNSS NOT PUBLISHED" if not gps.published else "NO FIX")
            return
        # Do not let retransmission of a cached GNSS timestamp refresh its age.
        key=gps.timestamp_utc or gps.sequence
        if key != self._last_key:
            self._last_key=key;self._last_gps_monotonic=gps.timestamp_monotonic_s
            self._last_gps=gps;self._has_gnss=True
            self.values["latitude"].setText(f"{gps.latitude:.6f}°")
            self.values["longitude"].setText(f"{gps.longitude:.6f}°")
            self.values["speed"].setText("--" if gps.speed_mps is None else f"{gps.speed_mps*2.236936:.1f} mph")
            self.values["satellites"].setText("—" if gps.satellites is None else f"◈  {gps.satellites}")
            self.values["accuracy"].setText("—" if gps.horizontal_accuracy_m is None else f"±{gps.horizontal_accuracy_m:.1f} m")
        self._missing=gps.state is DisplayState.STALE
        self.refresh_age()

    def refresh_age(self):
        self.age_s=None if self._last_gps_monotonic is None else max(0,time.monotonic()-self._last_gps_monotonic)
        if self.age_s is None or self.age_s>self.EXPIRE_AFTER:
            self.state="NO DATA"
            self.values["fix"].setText("NO FIX")
            if self.age_s is not None:
                for key in ("latitude","longitude","speed","satellites","accuracy"):self.values[key].setText("—")
        elif self._missing or self.age_s>self.STALE_AFTER:
            self.state="STALE"
            self.values["fix"].setText("STALE — GNSS UNAVAILABLE" if self._missing else "STALE")
        else:
            self.state="LIVE";self.values["fix"].setText("VALID")
        self.state_badge.set_state(self.state)
        self.values["age"].setText("—" if self.age_s is None else f"{self.age_s:.1f} s" + (" · STALE" if self.state=="STALE" else ""))

    def link_unavailable(self):
        self._missing=True;self.refresh_age()


class ConsoleBody(QWidget):
    """Layouts fill both columns; left width is constrained by the 4:3 content."""
    def __init__(self,left,right,cabin,speed):
        super().__init__()
        self.setObjectName("body")
        self.left,self.right,self.cabin,self.speed=left,right,cabin,speed
        self.focus=False
        layout=QHBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14)
        layout.addWidget(left);layout.addWidget(right,1)

    def arrange(self):
        height=self.height()
        if self.focus:
            width=min(self.width(),round((height-self.cabin.CHROME_HEIGHT)*4/3)+2)
        else:
            reserve=max(210,round(height*.29))
            width=min(round(self.width()*.49),round((height-reserve-14-self.cabin.CHROME_HEIGHT)*4/3)+2)
        width=max(320,width)
        self.left.setFixedWidth(width)
        self.cabin.setFixedHeight(self.cabin.height_for_width(width))

    def resizeEvent(self,event):
        super().resizeEvent(event);self.arrange()


class MinimalOperatorConsole(QMainWindow):
    def __init__(self,sources,map_factory=None):
        super().__init__()
        self.sources=sources
        self.mode="WAN" if getattr(sources.video,"mode","WAN")=="WAN" else "MOCK"
        self.started_at=time.monotonic()
        self.setWindowTitle("MILA · REMOTE VEHICLE OPERATOR CONSOLE")
        self.setMinimumSize(1080,740);self.resize(1360,900)
        self.setStyleSheet(PREMIUM_STYLE)
        self._process=psutil.Process();self._process.cpu_percent()
        self.cpu_samples=deque(maxlen=600);self.rss_samples=deque(maxlen=600)
        self.heartbeat_count=0;self.max_timer_delay_s=0;self._tick=time.monotonic()
        self._last_map_state=None
        self._closed=False
        self.course=CourseEstimator()
        root_widget=QWidget();root_widget.setObjectName("premiumRoot")
        root=QVBoxLayout(root_widget);root.setContentsMargins(18,12,18,16);root.setSpacing(14)
        header=QHBoxLayout();header.setSpacing(12)
        title=caption("MILA · REMOTE VEHICLE OPERATOR CONSOLE","consoleTitle");header.addWidget(title);header.addStretch()
        self.clock=caption("","muted");header.addWidget(self.clock)
        self.remote_badge=StatusPill("REMOTE LINK · READY",184);header.addWidget(self.remote_badge)
        self.fullscreen_button=button("FULLSCREEN",96);self.fullscreen_button.clicked.connect(self.toggle_fullscreen);header.addWidget(self.fullscreen_button)
        root.addLayout(header)

        left=QWidget();left_layout=QVBoxLayout(left);left_layout.setContentsMargins(0,0,0,0);left_layout.setSpacing(14)
        self.cabin=CabinVideoCard();left_layout.addWidget(self.cabin)
        self.speed_panel,speed_layout=card()
        speed_header=QHBoxLayout();speed_header.addWidget(caption("GROUND SPEED","sectionTitle"));speed_header.addStretch();speed_header.addWidget(caption("GNSS"));speed_layout.addLayout(speed_header)
        self.speedometer=SpeedometerWidget();speed_layout.addWidget(self.speedometer,1)
        status=QHBoxLayout();status.setSpacing(8)
        self.video_badge=StatusPill("CONNECTING")
        self.telemetry_badge=StatusPill("NO DATA")
        status.addWidget(caption("VIDEO LINK"));status.addWidget(self.video_badge);status.addStretch()
        status.addWidget(caption("GNSS"));status.addWidget(self.telemetry_badge)
        speed_layout.addLayout(status);left_layout.addWidget(self.speed_panel,1)

        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(0,0,0,0);right_layout.setSpacing(14)
        self.gps=MinimalGpsPanel();right_layout.addWidget(self.gps)
        map_panel,map_layout=card();map_layout.setContentsMargins(1,0,1,1);map_layout.setSpacing(0)
        map_header=QWidget();map_header.setFixedHeight(48);map_row=QHBoxLayout(map_header);map_row.setContentsMargins(16,0,12,0)
        map_row.addWidget(caption("NAVIGATION","sectionTitle"));map_row.addStretch()
        self.recenter_button=button("RECENTER",82);map_row.addWidget(self.recenter_button)
        self.perspective_button=button("3D",40);self.perspective_button.setCheckable(True);self.perspective_button.setChecked(True);map_row.addWidget(self.perspective_button)
        plus,minus=button("+",28),button("−",28);map_row.addWidget(minus);map_row.addWidget(plus)
        map_layout.addWidget(map_header)
        self.map=(map_factory or OnlineMapWidget)(demo=self.mode=="MOCK")
        map_layout.addWidget(self.map,1);right_layout.addWidget(map_panel,1)
        self.recenter_button.clicked.connect(self.map.recenter)
        self.perspective_button.toggled.connect(self.map.perspective)
        plus.clicked.connect(lambda:self.map.zoom(1));minus.clicked.connect(lambda:self.map.zoom(-1))
        lower,lower_layout=card();lower_layout.setContentsMargins(12,8,18,8)
        details=QHBoxLayout();details.setSpacing(18);self.compass=CourseIndicator()
        details.addWidget(self.compass);details.addWidget(self.gps.details,1);lower_layout.addLayout(details)
        right_layout.addWidget(lower)
        self.body=ConsoleBody(left,right,self.cabin,self.speed_panel);root.addWidget(self.body,1)
        self.setCentralWidget(root_widget)
        self.cabin.activated.connect(self.toggle_camera_focus)
        QShortcut(QKeySequence("F11"),self).activated.connect(self.toggle_fullscreen)
        QShortcut(QKeySequence("Escape"),self).activated.connect(self.restore_view)
        QShortcut(QKeySequence("F12"),self).activated.connect(self.capture_screenshot)
        sources.frame_ready.connect(self.on_frame);sources.camera_status.connect(self.on_camera_status)
        sources.telemetry_ready.connect(self.on_telemetry);sources.telemetry_status.connect(self.on_telemetry_status)
        sources.telemetry_failed.connect(lambda _:self.gps.link_unavailable())
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.refresh);self.timer.start()

    def start_sources(self):self.sources.start()

    @Slot(object)
    def on_frame(self,frame):
        if frame.camera_id is CameraId.CABIN:self.cabin.update_frame(frame)

    @Slot(object,object,str)
    def on_camera_status(self,camera_id,state,detail):
        if camera_id is CameraId.CABIN:self.cabin.set_stream_state(state)

    @Slot(object)
    def on_telemetry(self,state):
        self.gps.update_state(state.gps)
        if self.gps.state=="LIVE":
            heading=self.course.update(state.gps)
            self.compass.set_heading(heading)
            self.speedometer.set_speed_mps(state.gps.speed_mps)
            self.map.update_position(state.gps.latitude,state.gps.longitude,heading)
        self.refresh()

    @Slot(object)
    def on_telemetry_status(self,state):
        if state not in (DisplayState.LIVE,DisplayState.MOCK):self.gps.link_unavailable()

    def refresh(self):
        now=time.monotonic();self.heartbeat_count+=1
        self.max_timer_delay_s=max(self.max_timer_delay_s,max(0,now-self._tick-.2));self._tick=now
        self.gps.refresh_age();self.cabin.refresh_metrics()
        self.video_badge.set_state(self.cabin._stream_state)
        self.telemetry_badge.set_state(self.gps.state)
        self.speedometer.stale=self.gps.state=="STALE"
        if self.gps.state=="NO DATA":self.speedometer.set_speed_mps(None);self.compass.set_heading(None)
        self.speedometer.update()
        if self.gps.state != self._last_map_state and self.gps._last_gps is not None:
            gps=self.gps._last_gps
            self.map.update_position(gps.latitude,gps.longitude,self.course.heading,self.gps.state!="LIVE")
        self._last_map_state=self.gps.state
        state="LIVE" if self.gps.state=="LIVE" and self.cabin._stream_state=="LIVE" else "READY"
        self.remote_badge.set_state("SIMULATION" if self.mode=="MOCK" else "REMOTE LINK · "+state)
        self.clock.setText(datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
        if not self.rss_samples or now-self.rss_samples[-1][0]>1:
            self.cpu_samples.append(self._process.cpu_percent());self.rss_samples.append((now,self._process.memory_info().rss))

    def toggle_camera_focus(self):
        self.body.focus=not self.body.focus
        self.body.right.setVisible(not self.body.focus);self.speed_panel.setVisible(not self.body.focus)
        self.cabin.maximize_button.setText("BACK" if self.body.focus else "MAX")
        self.body.arrange()

    def toggle_fullscreen(self):
        if self.isFullScreen():self.showNormal()
        else:self.showFullScreen()
        self.fullscreen_button.setText("WINDOW" if self.isFullScreen() else "FULLSCREEN")

    def restore_view(self):
        if self.body.focus:self.toggle_camera_focus()
        if self.isFullScreen():self.toggle_fullscreen()

    def metrics(self):
        return {"mode":self.mode,"duration_s":time.monotonic()-self.started_at,
            "cabin_frames_rendered":self.cabin.rendered_frames,"cabin_fps":self.cabin.rendered_fps(),
            "gps_status":self.gps.state,"video_status":self.cabin._stream_state,
            "source_threads_running":self.sources.threads_running(),"map_bridge_updates":self.map.bridge_updates,
            "map_webengine":self.map.web is not None,"cpu_mean":sum(self.cpu_samples)/max(1,len(self.cpu_samples)),
            "rss_mib":self._process.memory_info().rss/1048576,"maximum_timer_delay_s":self.max_timer_delay_s}

    def capture_screenshot(self,output_path=None):
        path=Path(output_path) if output_path else Path("visualization/output/screenshots")/datetime.now(timezone.utc).strftime("console_%Y%m%dT%H%M%SZ.png")
        path.parent.mkdir(parents=True,exist_ok=True);self.grab().save(str(path),"PNG");return path

    def closeEvent(self,event):
        if not self._closed:
            self._closed=True;self.timer.stop();self.sources.stop();self.map.shutdown()
        super().closeEvent(event)
