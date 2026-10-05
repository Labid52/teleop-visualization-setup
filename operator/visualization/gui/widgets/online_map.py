"""MapLibre navigation with a bounded latest-position bridge and offline fallback."""

import json
import math
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QStackedLayout, QWidget


class MapFallback(QWidget):
    def __init__(self, demo=False, parent=None):
        super().__init__(parent)
        self.demo=demo
        self.position=None
        self.course=None
        self.phase=0.0

    def paintEvent(self, event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor("#eeece7"))
        if self.demo:
            p.save();p.translate(self.width()/2,self.height()*.45);p.shear(-.35,0);p.scale(1,.65)
            for i in range(-12,13):
                x=i*65-self.phase%65
                p.setPen(QPen(QColor("#8a98a3"),12));p.drawLine(int(x),-1000,int(x),1000);p.drawLine(-1000,int(x),1000,int(x))
                p.setPen(QPen(QColor("#ffffff"),8));p.drawLine(int(x),-1000,int(x),1000);p.drawLine(-1000,int(x),1000,int(x))
            p.restore()
        if self.position:
            p.save();p.translate(self.width()/2,self.height()/2);p.rotate(self.course or 0)
            p.setPen(QPen(QColor("#b5eaff"),2));p.setBrush(QColor("#64c6ef"))
            p.drawPolygon(QPolygonF([QPointF(0,-24),QPointF(15,18),QPointF(0,9),QPointF(-15,18)]));p.restore()
        p.setPen(QColor("#354f65"))
        p.drawText(16,25,"SIMULATION" if self.demo else "MAP UNAVAILABLE · POSITION REMAINS AVAILABLE")


class OnlineMapWidget(QWidget):
    def __init__(self, parent=None, demo=False, web_enabled=None):
        super().__init__(parent)
        self.demo=demo
        self.latitude=self.longitude=self.course=None
        self._latest=None
        self._dirty=False
        self._busy=False
        self._closed=False
        self.web=None
        self.bridge_updates=0
        self.engine_error=None
        self.fallback=MapFallback(demo,self)
        self.stack=QStackedLayout(self)
        self.stack.setContentsMargins(0,0,0,0)
        self.stack.addWidget(self.fallback)
        # Unit/offscreen tests do not launch a GPU browser or external network.
        self.web_enabled=(QApplication.platformName() not in ("offscreen","minimal")) if web_enabled is None else web_enabled
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self._deliver)
        self.timer.start()

    def showEvent(self,event):
        super().showEvent(event)
        if self.web_enabled and self.web is None and self.engine_error is None:
            self._start_web()

    def _start_web(self):
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
            self.profile=QWebEngineProfile(self)
            self.profile.setHttpUserAgent("MILA-Operator-Console/1.0 QtWebEngine")
            self.profile.setHttpCacheMaximumSize(32*1024*1024)
            self.web=QWebEngineView(self)
            self.page=QWebEnginePage(self.profile,self.web)
            self.page.setBackgroundColor(QColor("#f8f4f0"))
            self.web.setPage(self.page)
            self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,True)
            self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.web.loadFinished.connect(self._loaded)
            self.web.renderProcessTerminated.connect(lambda *_:self.stack.setCurrentWidget(self.fallback))
            self.stack.addWidget(self.web)
            url=QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1]/"assets"/"navigation.html"))
            if self.demo: url.setFragment("demo")
            self.web.load(url)
        except ImportError:
            self.engine_error="Qt WebEngine unavailable"

    def _loaded(self,ok):
        if self._closed: return
        self.stack.setCurrentWidget(self.web if ok else self.fallback)
        self._dirty=self._latest is not None

    def update_position(self,latitude,longitude,course=None,stale=False):
        if latitude is None or longitude is None: return
        if not all(math.isfinite(v) for v in (latitude,longitude)) or not (-90<=latitude<=90 and -180<=longitude<=180):return
        self.latitude,self.longitude,self.course=latitude,longitude,course
        self._latest={"lat":latitude,"lon":longitude,"course":course,"stale":bool(stale)}
        self._dirty=True
        self.fallback.position=(latitude,longitude);self.fallback.course=course
        self.fallback.phase=longitude*200000;self.fallback.update()

    def _deliver(self):
        if self._closed or not self._dirty or self._busy or self.web is None:return
        self._dirty=False;self._busy=True
        payload=json.dumps(self._latest,allow_nan=False)
        self.page.runJavaScript(f"typeof receivePosition === 'function' ? (receivePosition({payload}), true) : false",self._delivered)

    def _delivered(self,ok):
        self._busy=False
        if self._closed:return
        if ok:self.bridge_updates+=1
        else:self._dirty=True

    def recenter(self):
        if self.web:self.page.runJavaScript("window.recenter && recenter()")

    def zoom(self,delta):
        if self.web:self.page.runJavaScript(f"window.zoomMap && zoomMap({int(delta)})")

    def perspective(self,enabled):
        if self.web:self.page.runJavaScript("window.setPerspective && setPerspective("+str(bool(enabled)).lower()+")")

    def shutdown(self):
        self._closed=True;self.timer.stop()
        if self.web:
            self.web.stop()
            # Qt requires page destruction before its off-the-record profile.
            self.profile.setParent(QApplication.instance())
            self.page.destroyed.connect(self.profile.deleteLater)
            self.page.deleteLater()
