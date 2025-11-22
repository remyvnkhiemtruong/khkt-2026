from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton

from ..config import AppConfig


class SettingsTab(QWidget):
    def __init__(self, cfg: AppConfig, on_save_cb, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.on_save_cb = on_save_cb
        layout = QFormLayout(self)
        self.ed_mqtt_host = QLineEdit(self.cfg.mqtt.host)
        self.ed_mqtt_port = QLineEdit(str(self.cfg.mqtt.port))
        self.ed_http_port = QLineEdit(str(self.cfg.http.port))
        self.ed_api_key = QLineEdit(self.cfg.api_key or "")
        layout.addRow("MQTT Host", self.ed_mqtt_host)
        layout.addRow("MQTT Port", self.ed_mqtt_port)
        layout.addRow("HTTP Port", self.ed_http_port)
        layout.addRow("API Key", self.ed_api_key)
        self.btn_save = QPushButton("Save & Apply")
        layout.addRow(self.btn_save)
        self.btn_save.clicked.connect(self._on_save)

    def _on_save(self) -> None:
        self.cfg.mqtt.host = self.ed_mqtt_host.text().strip() or self.cfg.mqtt.host
        try:
            self.cfg.mqtt.port = int(self.ed_mqtt_port.text())
            self.cfg.http.port = int(self.ed_http_port.text())
        except Exception:
            pass
        self.cfg.api_key = self.ed_api_key.text().strip() or None
        self.cfg.save()
        if self.on_save_cb:
            self.on_save_cb(self.cfg)
