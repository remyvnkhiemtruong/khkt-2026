from __future__ import annotations

"""Application configuration and defaults.

Provides dataclasses and helpers to load/save runtime configuration.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import logging
from typing import Optional


log = logging.getLogger(__name__)


CONFIG_PATH = Path.home() / ".cmau_flood_caseA" / "config.json"


@dataclass
class MQTTConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    keepalive_s: int = 30
    topic_uplink: str = "cmau/flood/nodes/+/telemetry"


@dataclass
class HTTPConfig:
    host: str = "0.0.0.0"
    port: int = 8088
    enabled: bool = True


@dataclass
class Thresholds:
    q_max_m3s: float = 500.0
    spike_dh_dt_thresh: float = 0.05  # m per minute abnormal
    stuck_window_n: int = 12  # windows ~ 10m windows used downstream


@dataclass
class AppConfig:
    mqtt: MQTTConfig = MQTTConfig()
    http: HTTPConfig = HTTPConfig()
    thresholds: Thresholds = Thresholds()
    db_path: str = str((Path.home() / ".cmau_flood_caseA" / "data.sqlite").resolve())
    api_key: Optional[str] = None

    @staticmethod
    def load(path: Path = CONFIG_PATH) -> "AppConfig":
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                # naive merge to dataclasses
                mqtt = MQTTConfig(**data.get("mqtt", {}))
                http = HTTPConfig(**data.get("http", {}))
                thresholds = Thresholds(**data.get("thresholds", {}))
                cfg = AppConfig(mqtt=mqtt, http=http, thresholds=thresholds, db_path=data.get("db_path", AppConfig().db_path), api_key=data.get("api_key"))
                return cfg
        except Exception:
            log.exception("Failed to load config; using defaults")
        return AppConfig()

    def save(self, path: Path = CONFIG_PATH) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except Exception:
            log.exception("Failed to save config")
