from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from .config import load_preferences, save_preferences
from .env import load_env
from .ui.main_window import MainWindow


def main():
    load_env()
    prefs = load_preferences()
    app = QApplication(sys.argv)
    # load theme
    qss_path = Path(__file__).with_name("ui").joinpath("styles.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    win = MainWindow(prefs)
    win.show()
    code = app.exec()
    save_preferences(prefs)
    sys.exit(code)
