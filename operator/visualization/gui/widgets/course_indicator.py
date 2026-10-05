"""Compact course rose; no sensor or networking dependencies."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


class CourseIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading_deg = None
        self.setFixedSize(128, 116)

    def set_heading(self, value):
        self.heading_deg = None if value is None else value % 360
        self.update()

    def paintEvent(self, event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center=QPointF(64,53)
        p.setPen(QPen(QColor("#34526d"),1)); p.drawEllipse(center,42,42)
        p.setFont(QFont("DejaVu Sans",8))
        for label,deg in (("N",0),("E",90),("S",180),("W",270)):
            a=math.radians(deg-90); pos=QPointF(64+math.cos(a)*32,53+math.sin(a)*32)
            p.setPen(QColor("#94b3ce"));p.drawText(QRectF(pos.x()-7,pos.y()-7,14,14),Qt.AlignmentFlag.AlignCenter,label)
        if self.heading_deg is not None:
            p.save();p.translate(center);p.rotate(self.heading_deg)
            p.setPen(QPen(QColor("#cbf1ff"),1));p.setBrush(QColor("#68c9f7"))
            p.drawPolygon(QPolygonF([QPointF(0,-23),QPointF(9,13),QPointF(0,6),QPointF(-9,13)]));p.restore()
        p.setPen(QColor("#b0cbe0"));p.setFont(QFont("DejaVu Sans",8))
        p.drawText(QRectF(0,98,128,16),Qt.AlignmentFlag.AlignCenter,"COURSE —" if self.heading_deg is None else f"COURSE {self.heading_deg:03.0f}°")
