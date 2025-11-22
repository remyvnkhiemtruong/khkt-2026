from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget
import pyqtgraph as pg


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Risk tiles (simple labels)
        tiles = QHBoxLayout()
        self.labels = []
        for h in [3, 6, 9, 12, 24, 48, 72]:
            lab = QLabel(f"{h}h: —")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet("border:1px solid #ccc; padding:6px; border-radius:4px;")
            self.labels.append((h, lab))
            tiles.addWidget(lab)
        layout.addLayout(tiles)

        # Real-time plot
        self.plot = pg.PlotWidget()
        self.plot.setTitle("Water Level H (cm) & Discharge Q (m³/s)")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setClipToView(True)
        self.plot.setDownsampling(mode='peak')
        self.curve_H = self.plot.plot(pen=pg.mkPen('#2979ff', width=2), name='H (cm)')
        self.curve_Q = self.plot.plot(pen=pg.mkPen('#ff7043', width=2), name='Q (m3/s)')
        layout.addWidget(self.plot)

        # Latest alerts
        self.alerts = QListWidget()
        layout.addWidget(self.alerts)

    def update_risks(self, forecast: dict[int, dict]):
        for h, lab in self.labels:
            d = forecast.get(h)
            if d:
                p = d.get('prob_flood', 0.0)
                lab.setText(f"{h}h: {p:.0%}")

    def update_series(self, t: list[str], H_cm: list[float], Q: list[float]):
        try:
            x = list(range(len(t)))
            self.curve_H.setData(x, H_cm)
            self.curve_Q.setData(x, Q)
        except Exception:
            pass

    def set_alerts(self, lines: list[str]):
        self.alerts.clear()
        for s in lines:
            self.alerts.addItem(s)
