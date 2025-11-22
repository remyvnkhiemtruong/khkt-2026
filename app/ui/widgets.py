from __future__ import annotations

from PyQt6.QtWidgets import QLabel


class ValueLabel(QLabel):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setText(f"{title}: —")

    def set_value(self, title: str, value: str) -> None:
        self.setText(f"{title}: {value}")
