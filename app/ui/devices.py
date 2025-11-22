from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton


class DevicesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["node_id","last_seen","status","batt_v","rssi","fw_ver"])
        layout.addWidget(self.table)
        self.btn_test = QPushButton("Test kết nối")
        layout.addWidget(self.btn_test)

    def set_devices(self, rows: list[dict]):
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, k in enumerate(["node_id","last_seen","status","batt_v","rssi","fw_ver"]):
                self.table.setItem(i, j, QTableWidgetItem(str(r.get(k, ""))))
