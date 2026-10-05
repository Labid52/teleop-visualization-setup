"""No sender-state mirror has been validated; real mode supplies no controls."""

import threading
from visualization.gui.sources.base import OperatorStateSource


class NoOperatorStateSource(OperatorStateSource):
    def __init__(self):
        self._stop = threading.Event()

    def start(self):
        pass

    def get_latest(self):
        self._stop.wait(.1)
        return None

    def stop(self):
        self._stop.set()
