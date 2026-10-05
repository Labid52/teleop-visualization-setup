"""Sender-only presentation fixtures; never selected by WAN mode."""

from dataclasses import replace
import math
import time

import cv2
import numpy as np

from visualization.gui.models.ui_state import CameraId, DisplayState
from visualization.gui.sources.mock_video_source import MockVideoSource
from visualization.gui.sources.mock_telemetry_source import MockTelemetrySource


class ConsoleDemoTelemetry(MockTelemetrySource):
    def get_latest(self):
        state=super().get_latest()
        t=time.monotonic()-self._started_at
        angle=t/24
        fix=replace(state.gps,latitude=35+.001*math.sin(angle),longitude=-97+.001*math.cos(angle),
            speed_mps=max(0,7+4*math.sin(t/8)),heading_deg=math.degrees(-angle)%360,
            heading_source="GNSS COG",satellites=10+int(t/7)%4,horizontal_accuracy_m=1.2+.3*math.sin(t/5),
            fix_valid=int(t)%60<56,state=DisplayState.MOCK)
        return replace(state,gps=fix)


class ConsoleDemoVideo(MockVideoSource):
    def __init__(self):
        super().__init__(width=640,height=480,fps={CameraId.CABIN:10},enabled={CameraId.CABIN})

    @staticmethod
    def _style(camera_id,sequence,image):
        image[:]=(25,19,12)
        # Synthetic cabin illustration, clearly marked; no camera input or inference.
        cv2.fillConvexPoly(image,np.array([[55,100],[575,100],[525,260],[105,260]]),(54,43,29))
        for x in range(110,560,70):
            shift=sequence%70
            cv2.line(image,(x-shift,118),(x-shift-30,240),(64,53,36),2)
        cv2.rectangle(image,(55,260),(585,320),(47,35,24),-1)
        cv2.line(image,(70,275),(570,275),(116,91,55),2)
        center=(220,335);cv2.circle(image,center,83,(77,66,51),15)
        angle=.3*math.sin(sequence/18)
        for a in (angle,angle+2.1,angle+4.2):
            cv2.line(image,center,(int(220+70*math.cos(a)),int(335+70*math.sin(a))),(89,76,58),10)
        cv2.circle(image,center,24,(54,42,28),-1)
        for x in (445,505):cv2.rectangle(image,(x,361),(x+32,422),(68,56,39),-1)
        cv2.putText(image,"CABIN / SIMULATION",(24,34),cv2.FONT_HERSHEY_SIMPLEX,.52,(204,182,143),1,cv2.LINE_AA)
        cv2.putText(image,f"FRAME {sequence:06}",(465,454),cv2.FONT_HERSHEY_SIMPLEX,.4,(150,128,95),1,cv2.LINE_AA)
