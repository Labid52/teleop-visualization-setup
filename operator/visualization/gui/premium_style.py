"""Styles scoped to the compact operator console; full dashboard unchanged."""

PREMIUM_STYLE = """
QMainWindow, QWidget#premiumRoot, QWidget#body { background: #080f19; }
* { font-family: 'Inter', 'DejaVu Sans', sans-serif; color: #e4edf6; font-size: 12px; }
QFrame#premiumCard { background: #101c2b; border: 1px solid #23364b; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#consoleTitle { font-size: 17px; font-weight: 700; letter-spacing: 1px; }
QLabel#sectionTitle { color: #dfeaf5; font-size: 12px; font-weight: 700; letter-spacing: 2px; }
QLabel#caption { color: #8ba4be; font-size: 10px; font-weight: 600; letter-spacing: 1px; }
QLabel#coordinate { font-size: 31px; font-weight: 500; color: #eef7ff; }
QLabel#metric { font-size: 18px; font-weight: 600; color: #deefff; }
QLabel#muted { color: #8ba4be; font-size: 11px; }
QLabel#pill { font-size: 10px; font-weight: 700; border: 1px solid #2c4760;
 border-radius: 7px; background: #142638; color: #9cc6e5; padding: 0px; }
QLabel#pill[state='LIVE'] { background: #13342f; border-color: #28594c; color: #7de0b8; }
QLabel#pill[state='STALE'] { background: #392d1c; border-color: #645034; color: #eac384; }
QLabel#pill[state='NO DATA'] { background: #1a2838; border-color: #304255; color: #a4b5c9; }
QPushButton { background: #172c40; border: 1px solid #32516c; border-radius: 7px;
 color: #b9ddf4; font-size: 10px; font-weight: 600; padding: 0px; }
QPushButton:hover { background: #203c54; border-color: #61bce8; }
QPushButton:checked { background: #20445c; color: #b9ebff; }
"""
