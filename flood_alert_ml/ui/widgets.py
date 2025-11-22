from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QFrame

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
except Exception:  # pragma: no cover
    QWebEngineView = None

try:
    import pyqtgraph as pg  # type: ignore
except Exception:  # pragma: no cover
    pg = None


class RiskBadge(QLabel):
    def __init__(self):
        super().__init__("LOW")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setProperty("severity", "low")
        self.setMargin(4)

    def set_risk(self, label: str):
        self.setText(label)
        sev = "low"
        if label.upper() == "HIGH":
            sev = "high"
        elif label.upper().startswith("MOD"):
            sev = "mid"
        self.setProperty("severity", sev)
        self.style().unpolish(self)
        self.style().polish(self)


class StatCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("StatCard")
        v = QVBoxLayout(self)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.value = QLabel("0")
        self.value.setObjectName("CardValue")
        self.badge = RiskBadge()
        v.addWidget(self.title)
        v.addWidget(self.value)
        v.addWidget(self.badge)

    def set_value(self, text: str):
        self.value.setText(text)


class Toast(QWidget):
    def __init__(self, parent: QWidget, text: str, timeout_ms: int = 2500):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        v = QVBoxLayout(self)
        lbl = QLabel(text)
        v.addWidget(lbl)
        self.adjustSize()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close)
        self.timer.start(timeout_ms)


class MapWidget(QWidget):
        def __init__(self, lat: float, lon: float, zoom: int = 12):
                super().__init__()
                v = QVBoxLayout(self)
                if QWebEngineView is None:
                        lbl = QLabel("Bản đồ không khả dụng (chưa cài Qt WebEngine).")
                        v.addWidget(lbl)
                        self.web = None
                else:
                        self.web = QWebEngineView()
                        v.addWidget(self.web)
                        self._load_leaflet(lat, lon, zoom)

        def _leaflet_html(self, lat: float, lon: float, zoom: int) -> str:
                return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" />
    <style>
        html, body, #map {{ height: 100%; margin: 0; }}
    </style>
    <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>
    <script>
        let map, marker;
        function init() {{
            map = L.map('map').setView([{lat:.6f}, {lon:.6f}], {zoom});
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors'
            }}).addTo(map);
            marker = L.marker([{lat:.6f}, {lon:.6f}]).addTo(map);
        }}
        function setPos(lat, lon, zoom) {{
            map.setView([lat, lon], zoom);
            marker.setLatLng([lat, lon]);
        }}
        window.addEventListener('load', init);
    </script>
    <title>Map</title>
    </head>
<body>
    <div id=\"map\"></div>
</body>
</html>
"""

        def _load_leaflet(self, lat: float, lon: float, zoom: int):
                if not self.web:
                        return
                html = self._leaflet_html(lat, lon, zoom)
                self.web.setHtml(html)

        def set_location(self, lat: float, lon: float, zoom: int = 12):
                if not self.web:
                        return
                # call JS function to move marker and center
                js = f"setPos({lat:.6f}, {lon:.6f}, {zoom});"
                try:
                        self.web.page().runJavaScript(js)
                except Exception:
                        # if not ready yet, reload
                        self._load_leaflet(lat, lon, zoom)


class ChartWidget(QWidget):
        def __init__(self):
                super().__init__()
                v = QVBoxLayout(self)
                if pg is None:
                        lbl = QLabel("Cần cài pyqtgraph để hiển thị biểu đồ.")
                        v.addWidget(lbl)
                        self.top = None
                        self.bot = None
                        return
                self.top = pg.PlotWidget(title="Mưa tổng hợp (mm/h)")
                self.bot = pg.PlotWidget(title="Xác suất (%)")
                self.top.showGrid(x=True, y=True, alpha=0.3)
                self.bot.showGrid(x=True, y=True, alpha=0.3)
                v.addWidget(self.top)
                v.addWidget(self.bot)
                self.cur_precip = self.top.plot([], pen=pg.mkPen('#4ea1ff', width=2))
                self.cur_prob = self.bot.plot([], pen=pg.mkPen('#ffa640', width=2))

        def update_series(self, precip: list[float], probs: list[float]):
                if self.top is None or self.bot is None:
                        return
                xs = list(range(len(precip)))
                self.cur_precip.setData(xs, precip)
                xs2 = list(range(len(probs)))
                self.cur_prob.setData(xs2, probs)
