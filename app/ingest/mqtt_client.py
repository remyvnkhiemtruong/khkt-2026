from __future__ import annotations

"""MQTT client ingest using paho-mqtt."""

import json
import logging
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from ..storage.db import Database
from .telemetry_schema import validate_payload, process_payload


log = logging.getLogger(__name__)


class MQTTIngest:
    def __init__(self, db: Database, host: str, port: int, topic: str, username: Optional[str] = None, password: Optional[str] = None, keepalive: int = 30):
        self.db = db
        self.host = host
        self.port = port
        self.topic = topic
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self._client = mqtt.Client(client_id="cmau-flood-app", protocol=mqtt.MQTTv311, transport="tcp")
        if username:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._thread: threading.Thread | None = None

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc):  # type: ignore[no-untyped-def]
        if rc == 0:
            log.info("MQTT connected, subscribing %s", self.topic)
            client.subscribe(self.topic, qos=1)
        else:
            log.error("MQTT connect failed rc=%s", rc)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):  # type: ignore[no-untyped-def]
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            node_id, ts_iso, dist_m, rain_bin, batt_v, meta = validate_payload(payload)
            process_payload(self.db, node_id, ts_iso, dist_m, rain_bin, batt_v, meta)
        except Exception:
            log.exception("MQTT message process failed")

    def start(self) -> None:
        def _run():
            try:
                self._client.connect(self.host, self.port, keepalive=self.keepalive)
                self._client.loop_forever(retry_first_connection=True)
            except Exception:
                log.exception("MQTT loop failed")

        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=_run, name="MQTTIngest", daemon=True)
        self._thread.start()
