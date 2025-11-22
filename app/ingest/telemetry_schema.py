from __future__ import annotations

"""Telemetry schema validation and processing pipeline.

Payload example (Case A):
{
  "ts": "2025-11-03T09:15:00+07:00",
  "node_id": "CM-01",
  "s": { "dist_m": 0.83, "rain_bin": 1, "batt_v": 4.92 },
  "meta": { "sensor_height_above_crest_m": 0.95 },
  "ver": 2
}
"""

import logging
from typing import Any, Dict, Tuple

from ..storage.db import Database
from ..hq.hq_model import compute_h_q
from ..qc.rules import qc_flags


log = logging.getLogger(__name__)


def validate_payload(data: Dict[str, Any]) -> Tuple[str, str, float | None, int | None, float | None, dict]:
    """Validate minimal telemetry fields; returns tuple.

    Returns: (node_id, ts_iso, dist_m, rain_bin, batt_v, meta)
    Values may be None if missing; caller handles.
    """
    if not isinstance(data, dict):
        raise ValueError("payload must be object")
    node_id = str(data.get("node_id")) if data.get("node_id") else None
    ts = data.get("ts")
    s = data.get("s") or {}
    meta = data.get("meta") or {}
    dist = s.get("dist_m")
    rain_bin = s.get("rain_bin")
    batt_v = s.get("batt_v")
    if not node_id or not ts:
        raise ValueError("missing node_id or ts")
    try:
        ts_iso = str(ts)
        # fromisoformat can be too strict for offset colon variations; store string as-is
    except Exception as e:
        raise ValueError("invalid ts") from e
    dist_m = float(dist) if dist is not None else None
    rain_i = int(rain_bin) if rain_bin is not None else None
    batt = float(batt_v) if batt_v is not None else None
    return node_id, ts_iso, dist_m, rain_i, batt, meta


def process_payload(db: Database, node_id: str, ts_iso: str, dist_m: float | None, rain_bin: int | None, batt_v: float | None, meta: dict) -> dict:
    """Compute derived fields H, H_eff, Q, deltas, flags and upsert to DB.

    Returns the record stored for potential UI update.
    """
    # HQ params
    hq = db.get_hq(node_id)
    # Allow override of sensor height at meta if present
    sensor_h = float(meta.get("sensor_height_above_crest_m", hq.sensor_height_above_crest_m))

    H_m = None
    H_eff = None
    Q_m3s = None
    if dist_m is not None:
        H_m = sensor_h - dist_m
        H_eff = max(0.0, H_m - hq.H0_m)
        Q_m3s = compute_h_q(H_eff, hq.a, hq.b)

    # previous for deltas
    prev = db.value_10m_ago(node_id=node_id, ts_iso=ts_iso) or {}
    dH_10m = None
    dQ_10m = None
    if prev:
        try:
            if H_m is not None and prev.get("H_m") is not None:
                dH_10m = H_m - float(prev["H_m"])  # over ~10 minutes
            if Q_m3s is not None and prev.get("Q_m3s") is not None:
                dQ_10m = Q_m3s - float(prev["Q_m3s"])  # over ~10 minutes
        except Exception:
            log.exception("delta compute failed")

    flags = qc_flags(dist_m=dist_m, H_m=H_m, dH_10m=dH_10m, Q_m3s=Q_m3s)

    rec = {
        "node_id": node_id,
        "ts": ts_iso,
        "dist_m": dist_m,
        "H_m": H_m,
        "H_eff": H_eff,
        "Q_m3s": Q_m3s,
        "dH_10m": dH_10m,
        "dQ_10m": dQ_10m,
        "rain_bin": rain_bin,
        "batt_v": batt_v,
        "flags": flags,
    }
    try:
        db.upsert_telemetry(rec)
    except Exception:
        log.exception("DB upsert failed")
    return rec
