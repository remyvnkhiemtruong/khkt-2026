from __future__ import annotations

"""Alert evaluation based on rules.yaml with simple hysteresis/debounce memory."""

import time
from dataclasses import dataclass, field
from typing import Dict, Optional
import yaml

from ..storage.db import Database


@dataclass
class AlertState:
    last_ts: float = 0.0
    active_levels: Dict[str, bool] = field(default_factory=dict)


def load_rules(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def evaluate_and_store(db: Database, rules: dict, node_id: str, ts: str, forecasts: Dict[int, dict], dH_10m: Optional[float], rain_next_hour: Optional[float], state: AlertState) -> None:
    now = time.time()
    debounce_s = int(rules.get('debounce_min', 30)) * 60

    def _debounced(key: str) -> bool:
        return (now - state.last_ts) < debounce_s and state.active_levels.get(key, False)

    # Early rule
    early = rules.get('early', {})
    h_early = int(early.get('horizon_h', 6))
    prob_min = float(early.get('prob_min', 0.6))
    dh_min = float(early.get('dh10_min', 0.08))
    rain_min = float(early.get('rain_next_hour_mmph_min', 10.0))
    f_early = forecasts.get(h_early, {})
    if f_early and (float(f_early.get('prob_flood', 0.0)) >= prob_min or ((dH_10m or 0.0) >= dh_min and (rain_next_hour or 0.0) >= rain_min)):
        if not _debounced('early'):
            alert_id = f"{node_id}:{ts}:early:{h_early}"
            db.insert_alert(alert_id, ts, node_id, 'EARLY', h_early, 'rule:early')
            state.active_levels['early'] = True
            state.last_ts = now

    # High rule
    high = rules.get('high', {})
    h_high = int(high.get('horizon_h', 12))
    prob_high = float(high.get('prob_min', 0.7))
    f_high = forecasts.get(h_high, {})
    if f_high and float(f_high.get('prob_flood', 0.0)) >= prob_high:
        if not _debounced('high'):
            alert_id = f"{node_id}:{ts}:high:{h_high}"
            db.insert_alert(alert_id, ts, node_id, 'HIGH', h_high, 'rule:high')
            state.active_levels['high'] = True
            state.last_ts = now
