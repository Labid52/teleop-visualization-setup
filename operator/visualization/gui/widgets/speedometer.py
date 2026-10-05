"""GNSS speed dial. Unknown speed is never rendered as a measured zero."""

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SpeedometerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.speed_mph = None
        self.raw_mph = None
        self.stale = False
        self.setMinimumSize(240, 130)

    def set_speed_mps(self, speed_mps):
        self.raw_mph = None if speed_mps is None else max(0.0, speed_mps * 2.236936)
        if self.raw_mph is None:
            self.speed_mph = None
        elif self.raw_mph < .35:
            self.speed_mph = 0.0
        elif self.speed_mph is None or abs(self.raw_mph - self.speed_mph) >= .15:
            self.speed_mph = self.raw_mph
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width()/440, self.height()/215)
        p.translate((self.width()-440*scale)/2, (self.height()-215*scale)/2)
        p.scale(scale, scale)
        dial = QRectF(72, 24, 296, 296)
        p.setPen(QPen(QColor("#263d53"), 13))
        p.drawArc(dial, 0, 180*16)
        if self.speed_mph is not None:
            p.setPen(QPen(QColor("#dfb777" if self.stale else "#65c8f6"), 4))
            p.drawArc(dial.adjusted(-10,-10,10,10), 180*16, -round(min(80,self.speed_mph)/80*180*16))
        for value in range(0,81,5):
            angle = math.radians(180-value/80*180)
            def point(r): return QPointF(220+math.cos(angle)*r, 172-math.sin(angle)*r)
            p.setPen(QPen(QColor("#acc1d5" if value%10==0 else "#476078"), 2 if value%10==0 else 1))
            p.drawLine(point(132 if value%10==0 else 139), point(146))
            if value%10==0:
                pos=point(113)
                p.setFont(QFont("DejaVu Sans", 10))
                p.drawText(QRectF(pos.x()-18,pos.y()-9,36,18), Qt.AlignmentFlag.AlignCenter,str(value))
        if self.speed_mph is not None:
            angle=math.radians(180-min(80,self.speed_mph)/80*180)
            p.setPen(QPen(QColor("#90ddff"), 3))
            p.drawLine(QPointF(220+math.cos(angle)*133,172-math.sin(angle)*133),
                       QPointF(220+math.cos(angle)*160,172-math.sin(angle)*160))
        p.setPen(QColor("#efbe7b" if self.stale else "#eff7ff"))
        p.setFont(QFont("DejaVu Sans", 44, QFont.Weight.Light))
        p.drawText(QRectF(90,105,260,64),Qt.AlignmentFlag.AlignCenter,"—" if self.speed_mph is None else f"{self.speed_mph:.1f}")
        p.setFont(QFont("DejaVu Sans",10,QFont.Weight.Medium))
        p.setPen(QColor("#90abc3"))
        p.drawText(QRectF(90,172,260,20),Qt.AlignmentFlag.AlignCenter,"MPH" + ("  /  STALE" if self.stale else ""))
        p.setPen(QPen(QColor("#284157"),1))
        p.drawLine(12,199,428,199)
