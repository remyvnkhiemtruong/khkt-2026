from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any

from pydantic import BaseModel, Field, validator


APP_NAME = "FloodAlert"
DEFAULT_TZ = "Asia/Ho_Chi_Minh"
DEFAULT_LAT = 9.4350889
DEFAULT_LON = 105.4631939
DEFAULT_INTERVAL_MIN = 5
DEFAULT_INTERVAL_S = 30

HORIZONS = [3, 6, 9, 12, 24]


def get_config_dir() -> Path:
    if os.name == "nt":
        base = os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / APP_NAME
    else:
        return Path.home() / ".config" / APP_NAME


class Preferences(BaseModel):
    latitude: float = Field(DEFAULT_LAT)
    longitude: float = Field(DEFAULT_LON)
    # Deprecated: interval_min kept for backward compatibility
    interval_min: int = Field(DEFAULT_INTERVAL_MIN, ge=1, le=120)
    # New: interval in seconds
    interval_s: int = Field(DEFAULT_INTERVAL_S, ge=5, le=3600)
    enable_open_meteo: bool = True
    enable_open_weather: bool = True
    enable_simulator: bool = True
    enable_firebase_station: bool = True
    theme: str = Field("light")
    font_scale: float = Field(1.0)
    detailed_view: bool = Field(True)
    show_prob_bar: bool = Field(True)
    show_source_status: bool = Field(True)
    show_detail_group: bool = Field(True)
    show_horizon_cards: bool = Field(True)
    anonymize_coords: bool = False
    dynamic_scheduling: bool = False
    tz: str = Field(DEFAULT_TZ)
    # thresholds
    threshold_mm_h: float = 50.0
    thresholds_h: Dict[str, float] = Field(
        default_factory=lambda: {
            "3": 80.0,
            "6": 120.0,
            "9": 160.0,
            "12": 200.0,
            "24": 300.0,
        }
    )

    @validator("theme")
    def _v_theme(cls, v: str) -> str:
        return v if v in {"light", "dark"} else "light"


CONFIG_PATH = get_config_dir() / "config.json"


def load_preferences() -> Preferences:
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return Preferences(**data)
    except Exception:
        pass
    return Preferences()


def save_preferences(p: Preferences) -> None:
    cfg_dir = get_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    tmp = cfg_dir / "config.json.tmp"
    tmp.write_text(p.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

CSV_LOG_PATH = LOG_DIR / "flood_alert_log.csv"
XLSX_LOG_PATH = LOG_DIR / "flood_alert_log.xlsx"

# Exact schema columns
LOG_COLUMNS = [
    "timestamp_iso",
    "area_label",
    "latitude",
    "longitude",
    "open_meteo_precip_mm_h",
    "open_meteo_prob_pct",
    "openweather_precip_mm_h",
    "openweather_prob_pct",
    "simulator_precip_mm_h",
    # Firebase station fields
    "station_A_precip_mm_h",
    "station_A_flow_lpm",
    "station_A_float_active",
    "station_A_temp",
    "station_A_humidity",
    "aggregated_precip_mm_h",
    "trend_3pt_mm_h",
    "threshold_mm_h",
    "model_probability",
    "risk_label",
    "sources_available",
    "consensus_score",
    "degraded_flag",
    "location_source",
    "notes",
    # horizons 3, 6, 9, 12, 24
    "agg_total_precip_3h",
    "agg_max_intensity_3h",
    "mean_prob_3h",
    "prob_3h",
    "risk_3h",
    "agg_total_precip_6h",
    "agg_max_intensity_6h",
    "mean_prob_6h",
    "prob_6h",
    "risk_6h",
    "agg_total_precip_9h",
    "agg_max_intensity_9h",
    "mean_prob_9h",
    "prob_9h",
    "risk_9h",
    "agg_total_precip_12h",
    "agg_max_intensity_12h",
    "mean_prob_12h",
    "prob_12h",
    "risk_12h",
    "agg_total_precip_24h",
    "agg_max_intensity_24h",
    "mean_prob_24h",
    "prob_24h",
    "risk_24h",
]
