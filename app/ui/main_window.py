from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QWidget, QTabWidget, QVBoxLayout, QToolBar, QAction, QFileDialog

from ..config import AppConfig
from ..utils import ensure_logo, setup_logging
from ..storage.db import Database, HQParams
HTTPIngestServer = None  # lazy import
MQTTIngest = None  # lazy import
from ..model.service import ModelService
from ..workers.scheduler import Scheduler
from ..workers.alerting import load_rules, evaluate_and_store, AlertState
from ..api.weather import get_rain_next_hour_mmph
from .dashboard import DashboardTab
from .devices import DevicesTab
from .forecast_detail import ForecastTab
from .history_report import HistoryReportTab
from .settings import SettingsTab
from .hq_calib_dialog import HQCalibrationDialog


log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        setup_logging()
        self.cfg = cfg
        self.setWindowTitle("Cảnh báo sớm ngập úng – Case A (H–Q)")
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "logo.png"
        ensure_logo(icon_path)
        self.setWindowIcon(QIcon(str(icon_path)))

        # Services
        self.db = Database(self.cfg.db_path)
        self.model = ModelService()
        self.model.load(None)
        # HTTP ingest (optional if deps installed)
        self.http = None
        try:
            from ..ingest.http_server import HTTPIngestServer as _HTTP
            self.http = _HTTP(self.db, host=self.cfg.http.host, port=self.cfg.http.port)
            if self.cfg.http.enabled:
                self.http.start_in_background()
        except Exception:
            log.warning("HTTP ingest not started (missing deps?)")

        # MQTT ingest (optional)
        self.mqtt = None
        self._start_mqtt()

        # UI
        self.tabs = QTabWidget()
        self.dashboard = DashboardTab()
        self.devices = DevicesTab()
        self.forecast = ForecastTab()
        self.history = HistoryReportTab(self.db, node_id="CM-01")
        self.settings = SettingsTab(self.cfg, self._on_settings_apply)
        for i, w in enumerate([self.dashboard, self.devices, self.forecast, self.history, self.settings]):
            self.tabs.addTab(w, ["Dashboard","Devices","Forecast","History","Settings"][i])
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Toolbar
        tb = QToolBar("Main")
        self.addToolBar(tb)
        act_calib = QAction("H–Q Calibration", self)
        act_calib.triggered.connect(self._open_calib)
        tb.addAction(act_calib)

        # Rules & Scheduler
        self.rules = load_rules(str(Path(__file__).resolve().parent.parent / 'rules.yaml'))
        self._alert_state = AlertState()

        # Scheduler
        self.scheduler = Scheduler(self._ui_tick, self._model_tick, self._api_tick, self._maint_tick)

    # --- Ingest ---
    def _start_mqtt(self) -> None:
        try:
            from ..ingest.mqtt_client import MQTTIngest as _MQTT
            self.mqtt = _MQTT(self.db, host=self.cfg.mqtt.host, port=self.cfg.mqtt.port, topic=self.cfg.mqtt.topic_uplink, username=self.cfg.mqtt.username, password=self.cfg.mqtt.password, keepalive=self.cfg.mqtt.keepalive_s)
            self.mqtt.start()
        except Exception:
            log.warning("MQTT ingest not started (missing deps or connection failed)")

    # --- Scheduler callbacks ---
    def _ui_tick(self) -> None:
        # Update dashboard plot with recent telemetry for a default node
        node_id = "CM-01"
        rows = self.db.latest_telemetry(node_id, limit=300)
        t = [r["ts"] for r in rows]
        H_cm = [max(0.0, (r.get("H_m") or 0.0)) * 100.0 for r in rows]
        Q = [float(r.get("Q_m3s") or 0.0) for r in rows]
        self.dashboard.update_series(t, H_cm, Q)
        alerts = [f"{a['ts']} {a['node_id']} {a['level']} {a['horizon_h']}h {a['reason']}" for a in self.db.latest_alerts(limit=5)]
        self.dashboard.set_alerts(alerts)

        # Devices table
        # Simple query direct via sqlite cursor would be added; reuse telemetry last rows to populate
        dev_rows = []
        for r in rows[-5:]:
            dev_rows.append({"node_id": node_id, "last_seen": r.get("ts"), "status": "online", "batt_v": r.get("batt_v"), "rssi": "", "fw_ver": ""})
        self.devices.set_devices(dev_rows)

    def _model_tick(self) -> None:
        node_id = "CM-01"
        rows = self.db.latest_telemetry(node_id, limit=2)
        if not rows:
            return
        r = rows[-1]
        rain1h = 0.0  # could be set by API tick
        feats = {"H_m": r.get("H_m") or 0.0, "dH_10m": r.get("dH_10m"), "rain_next_hour": rain1h}
        horizons = [3,6,9,12,24,48,72]
        pred = self.model.predict(feats, horizons)
        self.dashboard.update_risks(pred)
        # Optionally store to DB (not strictly needed for demo)
        for h in horizons:
            d = pred[h]
            self.db.upsert_forecast(ts_run=r.get("ts"), horizon_h=h, node_id=node_id, prob_flood=float(d["prob_flood"]), wl_peak_cm=float(d["wl_peak_cm"]), ci_low=float(d["ci"][0]), ci_high=float(d["ci"][1]))
        # Alerts
        evaluate_and_store(self.db, self.rules, node_id=node_id, ts=r.get("ts"), forecasts=pred, dH_10m=r.get("dH_10m"), rain_next_hour=0.0, state=self._alert_state)

    def _api_tick(self) -> None:
        # Optional: invoke weather API and cache value somewhere (omitted persistent cache for brevity)
        try:
            _ = get_rain_next_hour_mmph(self.db, lat=9.176, lon=105.15, api_key=self.cfg.api_key)
        except Exception:
            pass

    def _maint_tick(self) -> None:
        # Placeholder for backups/retention
        pass

    # --- UI actions ---
    def _open_calib(self) -> None:
        def apply_fit(fit) -> None:
            node_id = "CM-01"
            p = HQParams(a=fit.a, b=fit.b, H0_m=fit.H0_m, sensor_height_above_crest_m=self.db.get_hq(node_id).sensor_height_above_crest_m)
            self.db.upsert_hq(node_id, p)

        dlg = HQCalibrationDialog(on_apply=apply_fit, parent=self)
        dlg.exec()

    def _on_settings_apply(self, cfg: AppConfig) -> None:
        # Restart HTTP/MQTT based on new settings
        try:
            from ..ingest.http_server import HTTPIngestServer as _HTTP
            self.http = _HTTP(self.db, host=cfg.http.host, port=cfg.http.port)
            if cfg.http.enabled:
                self.http.start_in_background()
        except Exception:
            log.warning("HTTP ingest restart failed")
        self._start_mqtt()
