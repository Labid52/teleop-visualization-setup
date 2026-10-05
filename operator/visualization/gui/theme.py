"""Professional dark console theme."""

STYLESHEET = r"""
* { font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif; color: #dce8f4; font-size: 12px; }
QMainWindow, QWidget#central { background: #070c12; }
QFrame#topBar { background: #0c141e; border-bottom: 1px solid #223349; }
QFrame#bottomBar { background: #0b121a; border-top: 1px solid #1d2b3d; }
QFrame#panel, QFrame#cameraTile { background: #0d151f; border: 1px solid #1c2b3c; border-radius: 10px; }
QFrame#statusCard { background: #0a1119; border: 1px solid #172637; border-radius: 6px; }
QFrame#cameraHeader { background: #101c28; border: none; border-bottom: 1px solid #203247; }
QLabel#appTitle { color: #f0f6fc; font-size: 19px; font-weight: 700; letter-spacing: 1px; }
QLabel#eyebrow { color: #688198; font-size: 9px; font-weight: 700; letter-spacing: 2px; }
QLabel#panelTitle { color: #e5eef7; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
QLabel#cameraName { color: #f2f7fc; font-size: 13px; font-weight: 700; letter-spacing: 1px; }
QLabel#cameraImage { background: #05080d; color: #43556a; border: none; }
QLabel#cameraMetric, QLabel#metricLabel, QLabel#bottomMetric { color: #71859a; font-size: 9px; font-weight: 600; letter-spacing: .5px; }
QLabel#metricValue { color: #dbe7f2; font-size: 11px; font-weight: 600; }
QLabel#stateBadge { padding: 3px 8px; border-radius: 7px; font-size: 9px; font-weight: 800; background: #233044; color: #9fb0c2; }
QLabel#stateBadge[state="MOCK"] { background: #16384b; color: #62c9ff; border: 1px solid #245b78; }
QLabel#stateBadge[state="LIVE"], QLabel#stateBadge[state="CONNECTED"] { background: #123c30; color: #55e0a4; border: 1px solid #216a54; }
QLabel#stateBadge[state="STALE"], QLabel#stateBadge[state="DEGRADED"] { background: #49351a; color: #ffc66d; border: 1px solid #765524; }
QLabel#stateBadge[state="OFFLINE"], QLabel#stateBadge[state="DISCONNECTED"] { background: #492128; color: #ff7b8a; border: 1px solid #743541; }
QLabel#modePill { background: #142536; border: 1px solid #28506c; color: #6dc8ff; padding: 6px 10px; border-radius: 8px; font-size: 9px; font-weight: 700; }
QLabel#clock { color: #90a4b8; font-family: monospace; font-size: 10px; padding: 0 9px; }
QLabel#speedValue { color: #f4f8fc; font-size: 38px; font-weight: 300; }
QLabel#speedUnit, QLabel#speedSI { color: #6f8498; font-size: 9px; font-weight: 700; letter-spacing: 1px; }
QLabel#pedalValue { color: #eaf3fb; font-size: 18px; font-weight: 700; }
QLabel#focusLabel { color: #45b8ff; font-size: 9px; font-weight: 800; }
QToolButton, QPushButton#captureButton { background: #152334; border: 1px solid #2a3e54; border-radius: 6px; padding: 5px 8px; color: #c8d8e8; }
QToolButton:hover, QPushButton#captureButton:hover { background: #20354b; border-color: #45b8ff; }
QFrame#buttonCard { background: #0a121a; border: 1px solid #26384b; border-radius: 7px; }
QFrame#buttonCard[pressed="true"] { background: #173e35; border: 1px solid #53dda2; }
QLabel#buttonName { color: #e9f1f8; font-size: 13px; font-weight: 800; }
QLabel#buttonAction { color: #70859a; font-size: 8px; font-weight: 600; }
QProgressBar { background: #101b27; border: 1px solid #27384a; border-radius: 5px; height: 11px; }
QProgressBar[accent="throttle"]::chunk { background: #45c990; border-radius: 4px; }
QProgressBar[accent="brake"]::chunk { background: #e16e68; border-radius: 4px; }
QListWidget#eventList { background: #090f16; border: 1px solid #172536; border-radius: 5px; color: #8fa5ba; font-family: monospace; font-size: 9px; padding: 4px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { width: 8px; background: #0a1119; }
QScrollBar::handle:vertical { background: #2a3b4e; border-radius: 4px; min-height: 30px; }
QSplitter::handle { background: #101b28; width: 5px; height: 5px; }
"""
