from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem


class ForecastTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["horizon_h","prob","wl_peak_cm","ci_low","ci_high"])
        layout.addWidget(self.table)

    def set_forecast(self, rows: list[dict]):
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, k in enumerate(["horizon_h","prob_flood","wl_peak_cm","ci_low","ci_high"]):
                self.table.setItem(i, j, QTableWidgetItem(str(r.get(k, ""))))
