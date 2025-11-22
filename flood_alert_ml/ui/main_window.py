from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QDialog,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QApplication,
    QProgressBar,
    QSplitter,
    QScrollArea,
    QSizePolicy,
    QHeaderView,
)

from ..aggregator import WeatherAggregator
from ..config import Preferences, HORIZONS, LOG_DIR, CSV_LOG_PATH, XLSX_LOG_PATH, save_preferences, load_preferences
from ..env import get_openweather_key, save_openweather_key
from ..features import compute_trend_mm_h, make_feature_vector, make_feature_vector_h
from ..geocode import GeoCoder
from ..geolocate import get_location
from ..logging_io import CSVLogger, ExcelLogger
from ..model import FloodRiskModel
from ..model_horizons import HorizonModels
from ..sources.open_meteo import OpenMeteoFetcher
from ..sources.open_weather import OpenWeatherFetcher
from ..sources.simulator import SimulatedFetcher
from ..sources.firebase_station import FirebaseStationFetcher
from ..utils import utc_now
from .widgets import StatCard, Toast, ChartWidget
from ..workers import ThreadPool


class MainWindow(QMainWindow):
    request_update = pyqtSignal()

    def __init__(self, prefs: Preferences):
        super().__init__()
        self.prefs = prefs
        self.setWindowTitle("Hệ thống Cảnh báo Ngập lụt (Flood Alert ML)")
        self.resize(1100, 720)

        # Services
        self.geocoder = GeoCoder()
        self.csv = CSVLogger()
        self.xlsx = ExcelLogger()
        self.fetchers = []
        if self.prefs.enable_open_meteo:
            self.fetchers.append(OpenMeteoFetcher())
        if self.prefs.enable_open_weather:
            self.fetchers.append(OpenWeatherFetcher())
        if self.prefs.enable_simulator:
            self.fetchers.append(SimulatedFetcher())
        if getattr(self.prefs, "enable_firebase_station", False):
            self.fetchers.append(FirebaseStationFetcher(station_id="station_A"))
        self.aggregator = WeatherAggregator(self.fetchers)
        self.model = FloodRiskModel(threshold_mm=self.prefs.threshold_mm_h)
        self.h_models = HorizonModels({h: float(self.prefs.thresholds_h[str(h)]) for h in HORIZONS})
        # Persistent thread pool and signal tracking
        self.tp = ThreadPool()
        self._pending_signals = []

        # State
        self.history = deque(maxlen=12)
        # Use seconds-based interval; fall back to minutes if missing
        self.countdown_s = int(getattr(self.prefs, "interval_s", 30))
        self.running = True
        self._in_flight = False
        self._last_rows = []

        # UI
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        self.header = QLabel("Khu vực: Tỉnh Cà Mau | Lần cập nhật: - | Còn lại: --:--")
        layout.addWidget(self.header)

        layout.addWidget(self._build_controls())

        # Hai panel theo chiều ngang cho 16:9
        split = QSplitter(Qt.Orientation.Horizontal)
        panel_left = QWidget(); left = QVBoxLayout(panel_left)
        panel_right = QWidget(); right = QVBoxLayout(panel_right)

        # Panel trái: Tổng quan
        self.cards = StatCard("Cường độ mưa tổng hợp (mm/h)")
        left.addWidget(self.cards)
        self.prog_prob = QProgressBar()
        self.prog_prob.setRange(0, 100)
        self.prog_prob.setFormat("Xác suất mô hình: %p%")
        self.prog_prob.setToolTip("Xác suất ngập do mô hình Logistic; màu sắc thay đổi theo mức rủi ro")
        left.addWidget(self.prog_prob)

        # Khối chỉ số đơn giản, thân thiện
        top_grid = QGridLayout()
        self.lbl_address = QLabel("Địa chỉ: -")
        self.lbl_sources = QLabel("Nguồn dữ liệu: Open-Meteo / OpenWeather / Mô phỏng")
        self.lbl_consensus = QLabel("Đồng nhất dữ liệu:")
        self.lbl_trend = QLabel("Xu hướng (3 điểm): 0.0 mm/h")
        top_grid.addWidget(self.lbl_address, 0, 0, 1, 2)
        top_grid.addWidget(self.lbl_sources, 1, 0, 1, 2)
        top_grid.addWidget(self.lbl_consensus, 2, 0)
        top_grid.addWidget(self.lbl_trend, 2, 1)
        right.addLayout(top_grid)
        # Kết luận hiện tại (thân thiện)
        self.lbl_verdict = QLabel("Kết luận hiện tại: -")
        left.addWidget(self.lbl_verdict)

        # Nút sao chép số liệu hiện tại
        btn_row = QHBoxLayout()
        self.bt_copy_metrics = QPushButton("Sao chép số liệu thực tế")
        btn_row.addStretch(1)
        btn_row.addWidget(self.bt_copy_metrics)
        right.addLayout(btn_row)
        def _copy_now():
            text = self._snapshot_text()
            QApplication.clipboard().setText(text)
            self.show_toast("Đã sao chép số liệu")
        self.bt_copy_metrics.clicked.connect(_copy_now)

        # Trạng thái theo nguồn (trực quan)
        self.box_src_status = QWidget()
        src_row = QHBoxLayout(self.box_src_status)
        src_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_src_om = QLabel("● Dữ liệu từ Open-Meteo: -")
        self.lbl_src_ow = QLabel("● Dữ liệu từ OpenWeather: -")
        self.lbl_src_sim = QLabel("● Dự liệu được mô phỏng bằng máy tính : -")
        self.lbl_src_station = QLabel("● Trạm A: -")
        for lbl in [self.lbl_src_om, self.lbl_src_ow, self.lbl_src_sim, self.lbl_src_station]:
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        for w in [self.lbl_src_om, self.lbl_src_ow, self.lbl_src_sim, self.lbl_src_station]:
            w.setToolTip("Màu chấm biểu thị mức rủi ro ước tính của nguồn")
        src_row.addWidget(self.lbl_src_om)
        src_row.addWidget(self.lbl_src_ow)
        src_row.addWidget(self.lbl_src_sim)
        src_row.addWidget(self.lbl_src_station)
        src_row.addStretch(1)
        right.addWidget(self.box_src_status)

        # Click handlers to show detailed info per source
        def _mk_click(name: str, title: str):
            def handler(event):
                try:
                    self._show_source_details(name, title)
                except Exception as e:
                    self.show_toast(str(e))
            return handler
        self.lbl_src_om.mousePressEvent = _mk_click('open_meteo', 'Open-Meteo')  # type: ignore[assignment]
        self.lbl_src_ow.mousePressEvent = _mk_click('openweather', 'OpenWeather')  # type: ignore[assignment]
        self.lbl_src_sim.mousePressEvent = _mk_click('simulator', 'Mô phỏng')  # type: ignore[assignment]
        self.lbl_src_station.mousePressEvent = _mk_click('station_station_A', 'Trạm quan trắc A')  # type: ignore[assignment]

        # Nhóm chỉ số chi tiết (ẩn/hiện theo chế độ xem)
        self.detail_group = QGroupBox("Chỉ số chi tiết")
        dg = QGridLayout(self.detail_group)
        dg.setHorizontalSpacing(10)
        dg.setVerticalSpacing(6)
        self.detail_labels = {}
        # helper để đặt nhãn theo 2 cột
        def add_item(idx: int, name: str, label: str):
            r = idx // 2
            c = (idx % 2) * 2
            dg.addWidget(QLabel(label), r, c)
            w = QLabel("-")
            w.setWordWrap(True)
            dg.addWidget(w, r, c + 1)
            self.detail_labels[name] = w
        items = [
            ("agg_precip", "Mưa tổng hợp tức thời (mm/h)"),
            ("trend", "Xu hướng 3 điểm (mm/h)"),
            ("threshold", "Ngưỡng tức thời (mm/h)"),
            ("prob", "Xác suất mô hình (%)"),
            ("risk", "Rủi ro hiện tại"),
            ("sources", "Nguồn khả dụng"),
            ("consensus", "Đồng thuận"),
            ("degraded", "Chất lượng"),
            ("notes", "Ghi chú"),
            ("om_precip", "Open-Meteo mưa (mm/h)"),
            ("om_prob", "Open-Meteo P (%)"),
            ("ow_precip", "OpenWeather mưa (mm/h)"),
            ("ow_prob", "OpenWeather P (%)"),
            ("sim_precip", "Mô phỏng mưa (mm/h)"),
        ]
        for i, (k, label) in enumerate(items):
            add_item(i, k, label)
        right.addWidget(self.detail_group)

        # Lưới đa chân trời
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(8)
        self.h_cards = {}
        r = 0
        for h in HORIZONS:
            card = StatCard(f"Dự báo {h} giờ")
            card.setToolTip("Tổng lượng mưa, cường độ cực đại và xác suất trong cửa sổ dự báo")
            card.set_value("Tổng=0.0 | Cực đại=0.0 | P=0%")
            card.badge.set_risk("LOW")
            self.h_cards[h] = card
            self.grid.addWidget(card, r // 3, r % 3)
            r += 1
        self.box_horizons = QWidget()
        self.box_horizons.setLayout(self.grid)
        right.addWidget(self.box_horizons)
        # lưu tham chiếu panel để tính kích thước
        self.panel_right = panel_right

        # Ghép vào splitter
        # panel phải đặt trong ScrollArea để thu nhỏ vẫn xem đủ
        scroll_right = QScrollArea()
        scroll_right.setWidget(panel_right)
        scroll_right.setWidgetResizable(True)
        self.scroll_right = scroll_right
        split.addWidget(panel_left)
        split.addWidget(scroll_right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setChildrenCollapsible(False)
        self.split = split
        layout.addWidget(split)

        self.tabs = QTabWidget()
        self.chart_tab = QWidget(); chart_layout = QVBoxLayout(self.chart_tab)
        self.chart = ChartWidget(); chart_layout.addWidget(self.chart)
        # Thứ tự tab ưu tiên sử dụng: Lịch sử, Files, Cài đặt, Thông tin
        self.tabs.addTab(self.chart_tab, "Lịch sử")
        self.tabs.addTab(self._build_files_tab(), "Files")
        self.tabs.addTab(self._build_settings_tab(), "Cài đặt")
        self.tabs.addTab(self._build_info_tab(), "Thông tin")
        layout.addWidget(self.tabs)
        # apply initial view mode visibility
        self._apply_view_mode()
        self._apply_visibility()
        # responsive: bố trí lại lưới chân trời theo độ rộng
        self._h_cols = 0
        QTimer.singleShot(0, self._rebuild_horizon_grid)

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

        # Initial update after show
        QTimer.singleShot(500, self.update_now)

    def _build_controls(self) -> QWidget:
        box = QGroupBox("Điều khiển")
        g = QGridLayout(box)
        # lat/lon
        g.addWidget(QLabel("Vĩ độ"), 0, 0)
        self.lat = QLineEdit(str(self.prefs.latitude))
        g.addWidget(self.lat, 0, 1)
        g.addWidget(QLabel("Kinh độ"), 0, 2)
        self.lon = QLineEdit(str(self.prefs.longitude))
        g.addWidget(self.lon, 0, 3)

        g.addWidget(QLabel("Chu kỳ (giây)"), 1, 0)
        self.interval = QSpinBox()
        self.interval.setRange(5, 3600)
        self.interval.setValue(int(getattr(self.prefs, "interval_s", 30)))
        g.addWidget(self.interval, 1, 1)

        g.addWidget(QLabel("Ngưỡng (mm/h)"), 1, 2)
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 500)
        self.threshold.setValue(int(self.prefs.threshold_mm_h))
        g.addWidget(self.threshold, 1, 3)

        self.bt_loc = QPushButton("Dùng vị trí của tôi")
        self.bt_loc.clicked.connect(self.use_my_location)
        g.addWidget(self.bt_loc, 2, 0)

        self.bt_start = QPushButton("Bắt đầu")
        self.bt_start.clicked.connect(self.start)
        g.addWidget(self.bt_start, 2, 1)
        self.bt_stop = QPushButton("Tạm dừng")
        self.bt_stop.clicked.connect(self.stop)
        g.addWidget(self.bt_stop, 2, 2)
        self.bt_update = QPushButton("Cập nhật ngay")
        self.bt_update.clicked.connect(self.update_now)
        g.addWidget(self.bt_update, 2, 3)

        # (API key moved to Tab Cài đặt)

        return box

    def show_toast(self, text: str):
        Toast(self, text).show()

    def _on_tick(self):
        if self.running:
            self.countdown_s -= 1
            if self.countdown_s <= 0:
                self.update_now()
        mm = self.countdown_s // 60
        ss = self.countdown_s % 60
        self.header.setText(
            f"Khu vực: {self._area_label()} | Lần cập nhật: {datetime.now().strftime('%H:%M:%S')} | Còn lại: {mm:02d}:{ss:02d}"
        )

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def _save_key(self):
        # Prefer the Settings tab field if available
        key_widget = getattr(self, "api_key_settings", None)
        if key_widget is None:
            return
        save_openweather_key(key_widget.text().strip())
        self.show_toast("Đã lưu mã API OpenWeather")

    def use_my_location(self):
        # run off-thread via thread pool to avoid blocking
        def task():
            return get_location()

        def on_ok(res):
            lat, lon, src = res
            if lat and lon:
                self.lat.setText(f"{lat:.6f}")
                self.lon.setText(f"{lon:.6f}")
                self.show_toast(f"Vị trí: {src.upper()}")
                self.lbl_address.setText(f"Địa chỉ: {self._area_label()}")
            else:
                self.show_toast("Không lấy được vị trí. Hãy bật quyền Vị trí trong Windows.")
            # release signal handle
            try:
                self._pending_signals.remove(sig)
            except Exception:
                pass

        sig = self.tp.submit(task)
        sig.success.connect(on_ok)
        try:
            self._pending_signals.append(sig)
        except Exception:
            pass

    def _area_label(self) -> str:
        try:
            lat = float(self.lat.text())
            lon = float(self.lon.text())
        except Exception:
            return "Xã Phước Long, tỉnh Cà Mau"
        lbl = self.geocoder.reverse(lat, lon)
        return lbl if lbl and lbl != "-" else "Xã Phước Long, tỉnh Cà Mau"

    def update_now(self):
        # debounce if countdown not finished but allow ad-hoc
        if self._in_flight:
            return
        self.bt_update.setEnabled(False)
        self.countdown_s = int(self.interval.value())
    # use persistent thread pool

        def pipeline():
            lat = float(self.lat.text())
            lon = float(self.lon.text())
            tz = self.prefs.tz
            rows = self.aggregator.fetch_all_parallel(lat, lon, tz)
            ag = self.aggregator.aggregate(rows)
            self.history.append(ag["aggregated_precip_mm_h"])
            trend = compute_trend_mm_h(self.history, 3)
            X = make_feature_vector(ag["aggregated_precip_mm_h"], trend, None)
            p = self.model.predict_proba(X)
            risk = "LOW" if p < 0.3 else ("MOD" if p < 0.6 else "HIGH")
            # horizon features using simple medians across source series
            series_list = [r.get("series", []) for r in rows if r.get("series")]
            if series_list:
                hourly = list(np.nanmedian(np.array([s + [np.nan] * (24 - len(s)) for s in series_list]), axis=0))
            else:
                hourly = [0.0] * 24
            # sanitize NaN/None to 0.0 for chart stability
            hourly = [0.0 if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x) for x in hourly]
            horizon_out = {}
            for h in HORIZONS:
                w = hourly[:h]
                total = float(np.nansum(w))
                mx = float(np.nanmax(w)) if w else 0.0
                Xh = make_feature_vector_h(total, mx, None)
                ph = self.h_models.predict_proba(h, Xh)
                rh = "LOW" if ph < 0.3 else ("MOD" if ph < 0.6 else "HIGH")
                horizon_out[h] = {"total": total, "max": mx, "prob": ph, "risk": rh}
            return {"rows": rows, "ag": ag, "trend": trend, "p": p, "risk": risk, "hourly": hourly, "h": horizon_out}

        def on_done(res: Dict[str, Any]):
            ag = res["ag"]
            rows = res.get("rows") or []
            # cache last rows for detail popups
            self._last_rows = rows

            # Rule-based override using hardware station
            hw_data = next((r for r in rows if str(r.get("source", "")).startswith("station_")), None)
            p = float(res.get("p") or 0.0)
            risk = str(res.get("risk") or "LOW")
            override_note = ""
            if hw_data:
                float_active = bool(hw_data.get("float_active", False))
                flow_val = hw_data.get("flow_lpm")
                try:
                    flow_lpm = float(flow_val if flow_val is not None else 0.0)
                except Exception:
                    flow_lpm = 0.0
                if float_active:
                    p = 1.0
                    risk = "HIGH"
                    override_note = " (CẢM BIẾN PHAO KÍCH HOẠT!)"
                elif flow_lpm > 50.0:
                    p = max(p, 0.85)
                    risk = "HIGH"
                    override_note = f" (LƯU LƯỢNG CAO: {flow_lpm} L/phút)"

            # Update headline with possibly overridden values
            self.cards.set_value(f"{ag['aggregated_precip_mm_h']:.1f} mm/h | Xác suất={p*100:.0f}%")
            self.cards.badge.set_risk(risk)
            # persist overridden values to result for logging + downstream UI
            res["p"] = p
            res["risk"] = risk
            if override_note:
                ag["notes"] = (ag.get("notes") or "") + override_note
            self.bt_update.setEnabled(True)
            self._append_logs(res)
            self._in_flight = False
            # cập nhật chỉ số chi tiết
            self.lbl_consensus.setText(f"Đồng thuận: {ag['consensus_score']:.2f}")
            self.lbl_trend.setText(f"Xu hướng (3 điểm): {res['trend']:.1f} mm/h")
            self.lbl_address.setText(f"Địa chỉ: {self._area_label()}")
            # bảng chi tiết
            if hasattr(self, 'detail_labels'):
                def setd(key, val):
                    lbl = self.detail_labels.get(key)
                    if lbl:
                        lbl.setText(val)
                setd('agg_precip', f"{ag['aggregated_precip_mm_h']:.1f}")
                setd('trend', f"{res['trend']:.1f}")
                setd('threshold', f"{float(self.threshold.value()):.1f}")
                setd('prob', f"{res['p']*100:.0f}")
                setd('risk', res['risk'])
                setd('sources', str(ag.get('sources_available', 0)))
                setd('consensus', f"{ag.get('consensus_score', 0.0):.2f}")
                setd('degraded', "Có suy giảm" if ag.get('degraded') else "Bình thường")
                setd('notes', ag.get('notes') or '-')
                # per-source quick look from rows
                rows = res.get('rows') or []
                def get_src(name, field):
                    for r in rows:
                        if r.get('source') == name:
                            return r.get(field)
                    return None
                om_p = get_src('open_meteo', 'precip_mm_h'); om_pb = get_src('open_meteo','precip_prob')
                ow_p = get_src('openweather', 'precip_mm_h'); ow_pb = get_src('openweather','precip_prob')
                sm_p = get_src('simulator', 'precip_mm_h')
                setd('om_precip', f"{om_p:.1f}" if om_p is not None else '-')
                setd('om_prob', f"{(om_pb or 0)*100:.0f}" if om_pb is not None else '-')
                setd('ow_precip', f"{ow_p:.1f}" if ow_p is not None else '-')
                setd('ow_prob', f"{(ow_pb or 0)*100:.0f}" if ow_pb is not None else '-')
                setd('sim_precip', f"{sm_p:.1f}" if sm_p is not None else '-')
            # cập nhật grid đa chân trời
            for h, hv in res["h"].items():
                txt = f"Tổng={hv['total']:.1f} | Cực đại={hv['max']:.1f} | P={hv['prob']*100:.0f}%"
                card = self.h_cards[h]
                card.set_value(txt)
                card.badge.set_risk(hv['risk'])
            # cập nhật trạng thái theo nguồn
            try:
                rows = res.get('rows') or []
                def get_src(name, field):
                    for r in rows:
                        if r.get('source') == name:
                            return r.get(field)
                    return None
                om_p = get_src('open_meteo', 'precip_mm_h'); om_pb = get_src('open_meteo','precip_prob')
                ow_p = get_src('openweather', 'precip_mm_h'); ow_pb = get_src('openweather','precip_prob')
                sm_p = get_src('simulator', 'precip_mm_h'); sm_pb = None
                st_p = get_src('station_station_A', 'precip_mm_h')
                st_float = get_src('station_station_A', 'float_active')
                st_pb = 1.0 if st_float else (0.5 if (st_p or 0) > 0 else 0.0)
                thr = float(self.threshold.value())
                self._set_src_label(self.lbl_src_om, 'Open-Meteo', om_p, om_pb, thr)
                self._set_src_label(self.lbl_src_ow, 'OpenWeather', ow_p, ow_pb, thr)
                self._set_src_label(self.lbl_src_sim, 'Mô phỏng', sm_p, sm_pb, thr)
                self._set_src_label(self.lbl_src_station, 'Trạm A', st_p, st_pb, thr)
                # Diagnostic tooltips for errors
                def get_meta_err(name: str):
                    for r in rows:
                        if r.get('source') == name:
                            m = r.get('meta') or {}
                            return m.get('error')
                    return None
                for lbl, src_name in [
                    (self.lbl_src_om, 'open_meteo'),
                    (self.lbl_src_ow, 'openweather'),
                    (self.lbl_src_sim, 'simulator'),
                    (self.lbl_src_station, 'station_station_A'),
                ]:
                    err = get_meta_err(src_name)
                    if err:
                        lbl.setToolTip(f"Lỗi nguồn: {err}")
                    else:
                        # keep existing tooltip text
                        if not lbl.toolTip().startswith('Màu chấm'):
                            lbl.setToolTip('Màu chấm biểu thị mức rủi ro ước tính của nguồn')
            except Exception:
                pass
            # cập nhật kết luận thân thiện
            self._update_verdict(res["risk"], res["p"])
            # cập nhật biểu đồ
            if hasattr(self, 'chart') and self.chart and res.get('hourly'):
                # precip series is 'hourly'; probs approximate from per-horizon prob mapped across window ends
                precip = res['hourly']
                # build a simple per-hour probability line: repeat last horizon prob or derive from instant p
                probs = [res['p']*100.0] * len(precip)
                self.chart.update_series(precip, probs)

        self._in_flight = True
        sig = self.tp.submit(pipeline)
        def on_err(msg: str):
            self.bt_update.setEnabled(True)
            self._in_flight = False
            try:
                self._pending_signals.remove(sig)
            except Exception:
                pass
            try:
                self.show_toast(msg)
            except Exception:
                pass
        sig.success.connect(on_done)
        try:
            sig.error.connect(on_err)
        except Exception:
            pass
        try:
            self._pending_signals.append(sig)
        except Exception:
            pass

    def _append_logs(self, res: Dict[str, Any]):
        ag = res["ag"]
        lat = float(self.lat.text())
        lon = float(self.lon.text())
        area = self._area_label()
        rows = res["rows"]
        def get_src(name: str, field: str):
            for r in rows:
                if r.get("source") == name:
                    return r.get(field)
            return None

        # Dữ liệu trạm (Firebase)
        station_data = {
            "station_A_precip_mm_h": get_src("station_station_A", "precip_mm_h"),
            "station_A_flow_lpm": get_src("station_station_A", "flow_lpm"),
            "station_A_float_active": get_src("station_station_A", "float_active"),
            "station_A_temp": get_src("station_station_A", "temperature"),
            "station_A_humidity": get_src("station_station_A", "humidity"),
        }

        row = {
            "timestamp_iso": datetime.now().astimezone().isoformat(),
            "area_label": area,
            "latitude": lat,
            "longitude": lon,
            "open_meteo_precip_mm_h": get_src("open_meteo", "precip_mm_h"),
            "open_meteo_prob_pct": get_src("open_meteo", "precip_prob"),
            "openweather_precip_mm_h": get_src("openweather", "precip_mm_h"),
            "openweather_prob_pct": get_src("openweather", "precip_prob"),
            "simulator_precip_mm_h": get_src("simulator", "precip_mm_h"),
            "aggregated_precip_mm_h": ag["aggregated_precip_mm_h"],
            "trend_3pt_mm_h": res["trend"],
            "threshold_mm_h": float(self.threshold.value()),
            "model_probability": res["p"],
            "risk_label": res["risk"],
            "sources_available": ag["sources_available"],
            "consensus_score": ag["consensus_score"],
            "degraded_flag": ag["degraded"],
            "location_source": "manual",
            "notes": ag["notes"],
        }
        # Thêm dữ liệu trạm vào log
        row.update(station_data)
        # horizons
        for h in HORIZONS:
            hres = res["h"][h]
            row.update({
                f"agg_total_precip_{h}h": hres["total"],
                f"agg_max_intensity_{h}h": hres["max"],
                f"mean_prob_{h}h": None,
                f"prob_{h}h": hres["prob"],
                f"risk_{h}h": hres["risk"],
            })
        # append
        try:
            self.csv.append(row)
            self.xlsx.append(row)
        except Exception:
            pass

    def _update_verdict(self, risk_label: str, prob: float):
        # Thông điệp đơn giản, dễ hiểu
        msg = "An toàn"
        color = "#2e7d32"  # green
        if risk_label.upper() == "HIGH":
            msg = "Rất dễ ngập"
            color = "#c62828"  # red
        elif risk_label.upper().startswith("MOD"):
            msg = "Cần chú ý"
            color = "#ef6c00"  # orange
        self.lbl_verdict.setText(f"Kết luận hiện tại: {msg} ({prob*100:.0f}%)")
        self.lbl_verdict.setStyleSheet(f"font-weight:600; padding:6px; border-radius:6px; background:{color}20; color:{color};")
        # cập nhật thanh xác suất
        self.prog_prob.setValue(int(prob * 100))
        # tô màu trực quan
        self.prog_prob.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_horizon_grid()

    def _rebuild_horizon_grid(self):
        try:
            avail = self.panel_right.width() if hasattr(self, 'panel_right') else self.width()
        except Exception:
            avail = self.width()
        # quyết định số cột theo độ rộng
        if avail >= 1600:
            cols = 4
        elif avail >= 1200:
            cols = 3
        elif avail >= 800:
            cols = 2
        else:
            cols = 1
        if getattr(self, '_h_cols', 0) == cols:
            return
        self._h_cols = cols
        i = 0
        for h in sorted(self.h_cards.keys()):
            card = self.h_cards[h]
            r = i // cols
            c = i % cols
            self.grid.addWidget(card, r, c)
            # đảm bảo statcard co giãn ngang
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            i += 1

    def _set_src_label(self, lbl: QLabel, name: str, precip: Optional[float], prob: Optional[float], threshold: float):
        txt_p = "-" if precip is None else f"{precip:.1f}"
        txt_pb = "-" if prob is None else f"{prob*100:.0f}%"
        lbl.setText(f"● {name}: {txt_p} mm/h | P={txt_pb}")
        # ước lượng mức màu
        score = 0.0
        if prob is not None:
            score = prob
        elif precip is not None and threshold > 0:
            ratio = precip / threshold
            score = 1.0 if ratio >= 1.0 else (0.6 if ratio >= 0.6 else 0.2)
        color = "#2e7d32" if score < 0.3 else ("#ef6c00" if score < 0.6 else "#c62828")
        lbl.setStyleSheet(f"color:{color}; font-weight:600")

    def _snapshot_text(self) -> str:
        lines = []
        lines.append(f"Khu vực: {self._area_label()}")
        lines.append(self.cards.value.text())
        lines.append(self.lbl_verdict.text())
        lines.append(self.lbl_consensus.text())
        lines.append(self.lbl_trend.text())
        # theo nguồn
        lines.append(self.lbl_src_om.text())
        lines.append(self.lbl_src_ow.text())
        lines.append(self.lbl_src_sim.text())
        lines.append(self.lbl_src_station.text())
        # đa chân trời
        for h, card in self.h_cards.items():
            lines.append(f"{card.title.text()}: {card.value.text()} | {card.badge.text()}")
        return "\n".join(lines)

    def _show_source_details(self, src_name: str, title: str) -> None:
        rows = getattr(self, '_last_rows', None) or []
        row = None
        for r in rows:
            if r.get('source') == src_name:
                row = r
                break
        if not row:
            self.show_toast("Chưa có dữ liệu cho nguồn này. Hãy cập nhật trước.")
            return
        # Helpers
        def fmt_float(v, nd=1):
            try:
                return f"{float(v):.{nd}f}"
            except Exception:
                return str(v)
        def fmt_bool(v):
            return "Bật" if bool(v) else "Tắt"

        lines: List[str] = []
        lines.append(f"Nguồn: {title}")
        ts = row.get('timestamp') or utc_now()
        lines.append(f"Thời gian: {ts}")

        # Field mappings (VN labels)
        # Note: precip_prob is 0..1; display as %
        fields = [
            ("precip_mm_h", "Cường độ mưa (mm/h)", lambda v: fmt_float(v, 1)),
            ("precip_prob", "Xác suất mưa (%)", lambda v: fmt_float((float(v) * 100.0) if v is not None else 0.0, 0)),
            ("flow_lpm", "Lưu lượng (L/phút)", lambda v: fmt_float(v, 1)),
            ("float_active", "Phao", lambda v: fmt_bool(v)),
            ("temperature", "Nhiệt độ (°C)", lambda v: fmt_float(v, 1)),
            ("humidity", "Độ ẩm (%)", lambda v: fmt_float(v, 1)),
        ]
        for key, label, f in fields:
            if key in row and row.get(key) is not None:
                lines.append(f"{label}: {f(row.get(key))}")

        # Series length (if available)
        series = row.get('series')
        if isinstance(series, list):
            lines.append(f"Chuỗi dữ liệu: {len(series)} điểm")

        # Meta details (VN labels)
        meta = row.get('meta') or {}
        if meta:
            lines.append("\nThông tin kết nối:")
            if meta.get('http_status') is not None:
                lines.append(f"  Mã HTTP: {meta.get('http_status')}")
            if meta.get('latency_ms') is not None:
                lines.append(f"  Độ trễ: {fmt_float(meta.get('latency_ms'), 0)} ms")
            if meta.get('error'):
                lines.append(f"  Lỗi: {meta.get('error')}")

        # Show dialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Chi tiết nguồn — {title}")
        v = QVBoxLayout(dlg)
        txt = QTextEdit(); txt.setReadOnly(True)
        txt.setPlainText("\n".join(lines))
        v.addWidget(txt)
        btns = QHBoxLayout(); v.addLayout(btns)
        btns.addStretch(1)
        bt_close = QPushButton("Đóng")
        def _close():
            try:
                dlg.close()
            except Exception:
                pass
        bt_close.clicked.connect(_close)
        btns.addWidget(bt_close)
        dlg.resize(520, 420)
        dlg.exec()

    # =========================
    # Tabs: Settings / Info / Files
    # =========================
    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        # Data sources
        self.cb_om = QCheckBox("Bật Open-Meteo")
        self.cb_ow = QCheckBox("Bật OpenWeather")
        self.cb_sim = QCheckBox("Bật Mô phỏng")
        self.cb_firebase = QCheckBox("Bật Trạm Quan trắc")
        self.cb_om.setChecked(self.prefs.enable_open_meteo)
        self.cb_ow.setChecked(self.prefs.enable_open_weather)
        self.cb_sim.setChecked(self.prefs.enable_simulator)
        self.cb_firebase.setChecked(getattr(self.prefs, "enable_firebase_station", False))
        row_src = QWidget(); row_src_l = QHBoxLayout(row_src); row_src_l.setContentsMargins(0,0,0,0)
        row_src_l.addWidget(self.cb_om); row_src_l.addWidget(self.cb_ow); row_src_l.addWidget(self.cb_sim); row_src_l.addWidget(self.cb_firebase); row_src_l.addStretch(1)
        form.addRow("Nguồn dữ liệu", row_src)

        # Test station connectivity (Firebase)
        station_row = QWidget(); station_h = QHBoxLayout(station_row); station_h.setContentsMargins(0,0,0,0)
        self.bt_test_station = QPushButton("Kiểm tra Trạm")
        self.lbl_station_test = QLabel("-")
        station_h.addWidget(self.bt_test_station)
        station_h.addWidget(self.lbl_station_test, 1)
        form.addRow("Trạm quan trắc", station_row)

        # OpenWeather API Key
        api_row = QWidget(); api_h = QHBoxLayout(api_row); api_h.setContentsMargins(0,0,0,0)
        self.api_key_settings = QLineEdit(get_openweather_key() or "")
        self.api_key_settings.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_settings.setPlaceholderText("Nhập OpenWeather API key")
        cb_show = QCheckBox("Hiển thị")
        bt_save_key = QPushButton("Lưu")
        bt_test_key = QPushButton("Kiểm tra")
        api_h.addWidget(self.api_key_settings, 1)
        api_h.addWidget(cb_show)
        api_h.addWidget(bt_save_key)
        api_h.addWidget(bt_test_key)
        form.addRow("OpenWeather API", api_row)

        # Interval (seconds) & theme
        self.sb_interval = QSpinBox(); self.sb_interval.setRange(5, 3600)
        self.sb_interval.setValue(int(getattr(self.prefs, "interval_s", getattr(self.prefs, "interval_min", 1) * 60)))
        form.addRow("Chu kỳ cập nhật (giây)", self.sb_interval)

        self.cmb_theme = QComboBox(); self.cmb_theme.addItems(["light", "dark"]); self.cmb_theme.setCurrentText(self.prefs.theme)
        form.addRow("Giao diện", self.cmb_theme)

        # View mode + font scale
        self.cb_detailed = QCheckBox("Giao diện chi tiết (hiển thị nhiều chỉ số)")
        self.cb_detailed.setChecked(bool(self.prefs.detailed_view))
        form.addRow("Chế độ xem", self.cb_detailed)

        self.dsb_font = QDoubleSpinBox(); self.dsb_font.setRange(0.8, 1.8); self.dsb_font.setSingleStep(0.05)
        self.dsb_font.setValue(float(self.prefs.font_scale or 1.0))
        form.addRow("Cỡ chữ", self.dsb_font)

        # Tùy chọn ẩn/bật các khối giao diện
        self.cb_prob_bar = QCheckBox("Hiển thị thanh xác suất")
        self.cb_prob_bar.setChecked(self.prefs.show_prob_bar)
        self.cb_src_status = QCheckBox("Hiển thị trạng thái theo nguồn")
        self.cb_src_status.setChecked(self.prefs.show_source_status)
        self.cb_detail_group = QCheckBox("Hiển thị nhóm chỉ số chi tiết")
        self.cb_detail_group.setChecked(self.prefs.show_detail_group)
        self.cb_h_cards = QCheckBox("Hiển thị thẻ dự báo đa chân trời")
        self.cb_h_cards.setChecked(self.prefs.show_horizon_cards)
        toggles_box = QWidget(); toggles_l = QHBoxLayout(toggles_box); toggles_l.setContentsMargins(0,0,0,0)
        toggles_l.addWidget(self.cb_prob_bar)
        toggles_l.addWidget(self.cb_src_status)
        toggles_l.addWidget(self.cb_detail_group)
        toggles_l.addWidget(self.cb_h_cards)
        toggles_l.addStretch(1)
        form.addRow("Ẩn/hiện thành phần", toggles_box)

        # Privacy & scheduling
        self.cb_anon = QCheckBox("Ẩn toạ độ khi ghi log")
        self.cb_anon.setChecked(self.prefs.anonymize_coords)
        form.addRow("Quyền riêng tư", self.cb_anon)

        self.cb_dynamic = QCheckBox("Lập lịch động theo tải và kết quả")
        self.cb_dynamic.setChecked(self.prefs.dynamic_scheduling)
        form.addRow("Lập lịch", self.cb_dynamic)

        # Timezone
        self.ed_tz = QLineEdit(self.prefs.tz)
        form.addRow("Múi giờ", self.ed_tz)

        # Thresholds
        self.dsb_thresh = QDoubleSpinBox(); self.dsb_thresh.setRange(0.0, 1000.0); self.dsb_thresh.setDecimals(1); self.dsb_thresh.setValue(float(self.prefs.threshold_mm_h))
        form.addRow("Ngưỡng tức thời (mm/h)", self.dsb_thresh)

        self.h_thresh = {}
        grid = QGridLayout();
        for i, h in enumerate(HORIZONS):
            dsb = QDoubleSpinBox(); dsb.setRange(0.0, 2000.0); dsb.setDecimals(1)
            dsb.setValue(float(self.prefs.thresholds_h.get(str(h), 100.0)))
            self.h_thresh[h] = dsb
            grid.addWidget(QLabel(f"{h} giờ"), i // 3, (i % 3) * 2)
            grid.addWidget(dsb, i // 3, (i % 3) * 2 + 1)
        box_thresh = QWidget(); box_thresh.setLayout(grid)
        form.addRow("Ngưỡng dự báo", box_thresh)

        # Buttons
        row_btn = QWidget(); hb = QHBoxLayout(row_btn); hb.setContentsMargins(0,0,0,0)
        bt_save = QPushButton("Lưu cài đặt"); bt_reload = QPushButton("Tải lại")
        hb.addStretch(1); hb.addWidget(bt_reload); hb.addWidget(bt_save)
        form.addRow("", row_btn)

        def do_save():
            # Update preferences and persist
            self.prefs.enable_open_meteo = self.cb_om.isChecked()
            self.prefs.enable_open_weather = self.cb_ow.isChecked()
            self.prefs.enable_simulator = self.cb_sim.isChecked()
            self.prefs.enable_firebase_station = self.cb_firebase.isChecked()
            self.prefs.interval_s = int(self.sb_interval.value())
            self.prefs.theme = self.cmb_theme.currentText()
            self.prefs.font_scale = float(self.dsb_font.value())
            self.prefs.detailed_view = bool(self.cb_detailed.isChecked())
            self.prefs.anonymize_coords = self.cb_anon.isChecked()
            self.prefs.dynamic_scheduling = self.cb_dynamic.isChecked()
            self.prefs.tz = self.ed_tz.text().strip() or self.prefs.tz
            self.prefs.threshold_mm_h = float(self.dsb_thresh.value())
            self.prefs.show_prob_bar = self.cb_prob_bar.isChecked()
            self.prefs.show_source_status = self.cb_src_status.isChecked()
            self.prefs.show_detail_group = self.cb_detail_group.isChecked()
            self.prefs.show_horizon_cards = self.cb_h_cards.isChecked()
            for h, dsb in self.h_thresh.items():
                self.prefs.thresholds_h[str(h)] = float(dsb.value())
            save_preferences(self.prefs)
            # apply to runtime
            self.interval.setValue(int(getattr(self.prefs, "interval_s", 30)))
            self.threshold.setValue(int(self.prefs.threshold_mm_h))
            self._rebuild_fetchers()
            self.apply_theme()
            self._apply_view_mode()
            self._apply_visibility()
            self.apply_font_scale()
            self.show_toast("Đã lưu cài đặt")

        def do_reload():
            p = load_preferences()
            self.cb_om.setChecked(p.enable_open_meteo)
            self.cb_ow.setChecked(p.enable_open_weather)
            self.cb_sim.setChecked(p.enable_simulator)
            self.cb_firebase.setChecked(getattr(p, "enable_firebase_station", False))
            self.sb_interval.setValue(int(getattr(p, "interval_s", getattr(p, "interval_min", 1) * 60)))
            self.cmb_theme.setCurrentText(p.theme)
            self.dsb_font.setValue(float(p.font_scale or 1.0))
            self.cb_detailed.setChecked(bool(p.detailed_view))
            self.cb_prob_bar.setChecked(p.show_prob_bar)
            self.cb_src_status.setChecked(p.show_source_status)
            self.cb_detail_group.setChecked(p.show_detail_group)
            self.cb_h_cards.setChecked(p.show_horizon_cards)
            self.cb_anon.setChecked(p.anonymize_coords)
            self.cb_dynamic.setChecked(p.dynamic_scheduling)
            self.ed_tz.setText(p.tz)
            self.dsb_thresh.setValue(float(p.threshold_mm_h))
            for h, dsb in self.h_thresh.items():
                dsb.setValue(float(p.thresholds_h.get(str(h), dsb.value())))
            # also update prefs in memory and apply visibility
            self.prefs = p
            self._apply_view_mode()
            self._apply_visibility()
            self.show_toast("Đã tải lại cài đặt")

        bt_save.clicked.connect(do_save)
        bt_reload.clicked.connect(do_reload)

        def on_show_toggled(checked: bool):
            self.api_key_settings.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        cb_show.toggled.connect(on_show_toggled)

        bt_save_key.clicked.connect(self._save_key)

        def do_test():
            self._save_key()  # ensure saved first
            from ..workers import ThreadPool
            def task():
                try:
                    lat = float(self.lat.text()); lon = float(self.lon.text())
                except Exception:
                    lat, lon = 10.762622, 106.660172
                try:
                    fetcher = OpenWeatherFetcher()
                    res = fetcher.fetch(lat, lon, self.prefs.tz)
                    return None if res.get("error") else True
                except Exception as e:
                    return False
            def done(ok):
                if ok:
                    self.show_toast("API hợp lệ và truy cập được")
                else:
                    self.show_toast("Không kiểm tra được API. Vui lòng kiểm tra key/mạng")
            tp = ThreadPool(); sig = tp.submit(task); sig.success.connect(done)
        bt_test_key.clicked.connect(do_test)

        # Handler: test Firebase station
        def do_test_station():
            try:
                self.bt_test_station.setEnabled(False)
                self.lbl_station_test.setText("Đang kiểm tra…")
            except Exception:
                pass
            def task():
                try:
                    fetcher = FirebaseStationFetcher(station_id="station_A")
                    res = fetcher.fetch(0.0, 0.0, self.prefs.tz)
                    return res
                except Exception as e:
                    return {"error": str(e)}
            def done(res: Dict[str, Any]):
                try:
                    meta = res.get("meta") if isinstance(res, dict) else None
                    err = (res.get("error") if isinstance(res, dict) else None) or ((meta or {}).get("error") if isinstance(meta, dict) else None)
                    if err:
                        self.lbl_station_test.setText(f"Lỗi: {err}")
                        self.lbl_station_test.setStyleSheet("color:#c62828; font-weight:600")
                        self.show_toast("Không kết nối được trạm")
                    else:
                        precip = res.get("precip_mm_h") if isinstance(res, dict) else None
                        flow = res.get("flow_lpm") if isinstance(res, dict) else None
                        flt = res.get("float_active") if isinstance(res, dict) else None
                        txt = []
                        if precip is not None:
                            try:
                                txt.append(f"mưa={float(precip):.1f} mm/h")
                            except Exception:
                                pass
                        if flow is not None:
                            try:
                                txt.append(f"lưu lượng={float(flow):.1f} L/phút")
                            except Exception:
                                pass
                        if flt is not None:
                            txt.append("phao=ON" if bool(flt) else "phao=OFF")
                        if not txt:
                            txt.append("OK")
                        self.lbl_station_test.setText(" | ".join(txt))
                        self.lbl_station_test.setStyleSheet("color:#2e7d32; font-weight:600")
                        self.show_toast("Kết nối trạm OK")
                finally:
                    try:
                        self.bt_test_station.setEnabled(True)
                    except Exception:
                        pass
                    try:
                        self._pending_signals.remove(sig)
                    except Exception:
                        pass
            sig = self.tp.submit(task)
            sig.success.connect(done)
            try:
                self._pending_signals.append(sig)
            except Exception:
                pass
        self.bt_test_station.clicked.connect(do_test_station)
        return w

    def _rebuild_fetchers(self):
        self.fetchers = []
        if self.prefs.enable_open_meteo:
            self.fetchers.append(OpenMeteoFetcher())
        if self.prefs.enable_open_weather:
            self.fetchers.append(OpenWeatherFetcher())
        if self.prefs.enable_simulator:
            self.fetchers.append(SimulatedFetcher())
        if getattr(self.prefs, "enable_firebase_station", False):
            self.fetchers.append(FirebaseStationFetcher(station_id="station_A"))
        self.aggregator = WeatherAggregator(self.fetchers)

    def apply_theme(self):
        app = QApplication.instance()
        if not app:
            return
        try:
            from pathlib import Path
            qss_path = Path(__file__).with_name("styles.qss")
            if self.prefs.theme == "dark" and qss_path.exists():
                app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
            else:
                app.setStyleSheet("")
        except Exception:
            pass

    def apply_font_scale(self):
        app = QApplication.instance()
        if not app:
            return
        f = app.font()
        base = float(self.prefs.font_scale or 1.0)
        f.setPointSizeF(max(8.0, f.pointSizeF() * (base / 1.0)))
        app.setFont(f)

    def _apply_view_mode(self):
        detailed = getattr(self, "cb_detailed", None)
        if detailed is None:
            return
        on = detailed.isChecked()
        # Toggle some detailed widgets
        for lab in [self.lbl_consensus, self.lbl_trend]:
            lab.setVisible(on)
        for lab in self.h_cards.values():
            lab.setVisible(on)
        # nhóm chi tiết
        if hasattr(self, 'detail_group'):
            self.detail_group.setVisible(on)

    def _apply_visibility(self):
        # Centralized control for visibility toggles from preferences/settings
        try:
            show_prob = bool(self.prefs.show_prob_bar)
            show_src = bool(self.prefs.show_source_status)
            show_detail = bool(self.prefs.show_detail_group)
            show_h = bool(self.prefs.show_horizon_cards)
            if hasattr(self, 'prog_prob'):
                self.prog_prob.setVisible(show_prob)
            if hasattr(self, 'box_src_status'):
                self.box_src_status.setVisible(show_src)
            if hasattr(self, 'detail_group'):
                self.detail_group.setVisible(show_detail)
            if hasattr(self, 'box_horizons'):
                self.box_horizons.setVisible(show_h)
        except Exception:
            pass

    def _build_info_tab(self) -> QWidget:
        import platform, sys
        from importlib import metadata

        w = QWidget(); v = QVBoxLayout(w)
        txt = QTextEdit(); txt.setReadOnly(True)
        def get_ver(pkg):
            try:
                return metadata.version(pkg)
            except Exception:
                return "-"
        info = []
        info.append("Sản phẩm: Flood Alert ML System")
        info.append(f"Phiên bản: {get_ver('flood_alert_ml')}")
        info.append(f"Python: {sys.version.split()[0]}")
        info.append(f"Hệ điều hành: {platform.platform()}")
        info.append("\nThư viện:")
        for lib in ["PyQt6", "requests", "numpy", "scikit-learn", "openpyxl"]:
            info.append(f"- {lib}: {get_ver(lib)}")
        txt.setText("\n".join(info))
        v.addWidget(txt)

        hb = QHBoxLayout(); v.addLayout(hb)
        bt_copy = QPushButton("Sao chép thông tin")
        hb.addStretch(1); hb.addWidget(bt_copy)
        def do_copy():
            txt.selectAll(); txt.copy(); txt.moveCursor(txt.textCursor().End)
            self.show_toast("Đã sao chép vào clipboard")
        bt_copy.clicked.connect(do_copy)
        return w

    def _build_files_tab(self) -> QWidget:
        import os
        from pathlib import Path
        import csv

        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel(f"Thư mục log: {LOG_DIR}"))

        hb = QHBoxLayout(); v.addLayout(hb)
        bt_folder = QPushButton("Mở thư mục")
        bt_csv = QPushButton("Mở CSV")
        bt_xlsx = QPushButton("Mở Excel")
        bt_refresh = QPushButton("Làm mới")
        bt_analyze = QPushButton("Phân tích nhanh")
        bt_report = QPushButton("Xuất báo cáo ngắn")
        hb.addWidget(bt_folder); hb.addWidget(bt_csv); hb.addWidget(bt_xlsx); hb.addWidget(bt_analyze); hb.addWidget(bt_report); hb.addStretch(1); hb.addWidget(bt_refresh)

        v.addWidget(QLabel("Chế độ xem: Xem trước CSV"))
        self.table = QTableWidget(); self.table.setRowCount(0); self.table.setColumnCount(0)
        v.addWidget(self.table, 1)

        # Kết quả phân tích hiển thị ở dưới bảng
        self.analysis = QTextEdit(); self.analysis.setReadOnly(True)
        v.addWidget(self.analysis)

        def open_path(p: Path):
            try:
                os.startfile(str(p))
            except Exception:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

        def refresh_table():
            self.table.clear()
            if not CSV_LOG_PATH.exists():
                self.table.setRowCount(0); self.table.setColumnCount(0)
                return
            try:
                with CSV_LOG_PATH.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    rows = []
                    for i, row in enumerate(reader):
                        rows.append(row)
                        if i > 100:
                            break
                if not rows:
                    return
                headers = rows[0]
                data = rows[1:]
                self.table.setColumnCount(len(headers))
                self.table.setHorizontalHeaderLabels(headers)
                self.table.setRowCount(len(data))
                for r, row in enumerate(data):
                    for c, val in enumerate(row):
                        self.table.setItem(r, c, QTableWidgetItem(val))
            except Exception:
                pass

        def do_open_folder():
            open_path(LOG_DIR)

        def do_open_csv():
            if CSV_LOG_PATH.exists():
                open_path(CSV_LOG_PATH)
            else:
                self.show_toast("Chưa có file CSV")

        def do_open_xlsx():
            if XLSX_LOG_PATH.exists():
                open_path(XLSX_LOG_PATH)
            else:
                self.show_toast("Chưa có file Excel")

        bt_folder.clicked.connect(do_open_folder)
        bt_csv.clicked.connect(do_open_csv)
        bt_xlsx.clicked.connect(do_open_xlsx)
        bt_refresh.clicked.connect(refresh_table)
        
        def do_analyze():
            try:
                if not CSV_LOG_PATH.exists():
                    self.show_toast("Chưa có file CSV để phân tích")
                    return
                # đơn giản: lấy hàng cuối cùng và kết luận
                import csv as _csv
                with CSV_LOG_PATH.open("r", encoding="utf-8", newline="") as f:
                    rows = list(_csv.DictReader(f))
                if not rows:
                    self.show_toast("CSV trống")
                    return
                last = rows[-1]
                prob = float(last.get("model_probability") or 0.0)
                risk = last.get("risk_label", "LOW")
                verdict = "An toàn" if risk=="LOW" and prob<0.3 else ("Cần chú ý" if risk.startswith("MOD") or 0.3<=prob<0.6 else "Rất dễ ngập")
                lines = [
                    f"Kết luận: {verdict} (≈ {prob*100:.0f}%)",
                    f"3h: {last.get('risk_3h','-')} | 6h: {last.get('risk_6h','-')} | 9h: {last.get('risk_9h','-')} | 12h: {last.get('risk_12h','-')} | 24h: {last.get('risk_24h','-')}"
                ]
                self.analysis.setPlainText("\n".join(lines))
                self._update_verdict(risk, prob)
            except Exception as e:
                self.show_toast(str(e))
        bt_analyze.clicked.connect(do_analyze)

        def do_report():
            try:
                if not XLSX_LOG_PATH.exists():
                    self.show_toast("Chưa có Excel để xuất báo cáo")
                    return
                # mở thẳng file Excel cho người dùng (đơn giản và quen thuộc)
                open_path(XLSX_LOG_PATH)
            except Exception as e:
                self.show_toast(str(e))
        bt_report.clicked.connect(do_report)

        # initial load
        QTimer.singleShot(0, refresh_table)
        return w
