from __future__ import annotations

"""Entry point to run the PyQt6 application."""

import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from .config import AppConfig
from .ui.main_window import MainWindow


def main() -> None:
    cfg = AppConfig.load()
    app = QApplication(sys.argv)
    # Load theme if available
    try:
        theme_path = Path(__file__).resolve().parent / 'ui' / 'theme.qss'
        if theme_path.exists():
            app.setStyleSheet(theme_path.read_text(encoding='utf-8'))
    except Exception:
        pass
    w = MainWindow(cfg)
    w.resize(1100, 700)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
