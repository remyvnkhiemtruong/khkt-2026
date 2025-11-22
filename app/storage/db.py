from __future__ import annotations

"""SQLite database access and schema management.

Implements upserts for telemetry, hq_profile, forecast, alerts, devices, api_cache.
"""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from datetime import datetime, timedelta

from ..utils import TZ_PLUS7


log = logging.getLogger(__name__)


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS telemetry(
      node_id TEXT,
      ts TEXT,
      dist_m REAL,
      H_m REAL,
      H_eff REAL,
      Q_m3s REAL,
      dH_10m REAL,
      dQ_10m REAL,
      rain_bin INTEGER,
      batt_v REAL,
      flags TEXT,
      PRIMARY KEY(node_id, ts)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS forecast(
      ts_run TEXT,
      horizon_h INTEGER,
      node_id TEXT,
      prob_flood REAL,
      wl_peak_cm REAL,
      ci_low REAL,
      ci_high REAL,
      PRIMARY KEY(ts_run, horizon_h, node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hq_profile(
      node_id TEXT PRIMARY KEY,
      a REAL,
      b REAL,
      H0_m REAL,
      sensor_height_above_crest_m REAL,
      updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts(
      alert_id TEXT PRIMARY KEY,
      ts TEXT,
      node_id TEXT,
      level TEXT,
      horizon_h INTEGER,
      reason TEXT,
      ack_by TEXT,
      ack_ts TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS devices(
      node_id TEXT PRIMARY KEY,
      last_seen TEXT,
      rssi INTEGER,
      batt_v REAL,
      fw_ver TEXT,
      status TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS api_cache(
      source TEXT,
      valid_from TEXT,
      valid_to TEXT,
      payload_hash TEXT,
      stored_at TEXT,
      payload BLOB
    )
    """,
]


@dataclass
class HQParams:
    a: float = 1.0
    b: float = 1.5
    H0_m: float = 0.0
    sensor_height_above_crest_m: float = 1.0


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        self._conn.commit()

    # --- HQ profile ---
    def get_hq(self, node_id: str) -> HQParams:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT a,b,H0_m,sensor_height_above_crest_m FROM hq_profile WHERE node_id=?",
            (node_id,)
        ).fetchone()
        if row:
            return HQParams(a=row[0], b=row[1], H0_m=row[2], sensor_height_above_crest_m=row[3])
        return HQParams()

    def upsert_hq(self, node_id: str, p: HQParams) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO hq_profile(node_id, a, b, H0_m, sensor_height_above_crest_m, updated_at)
            VALUES(?,?,?,?,?,datetime('now'))
            ON CONFLICT(node_id) DO UPDATE SET a=excluded.a, b=excluded.b, H0_m=excluded.H0_m,
              sensor_height_above_crest_m=excluded.sensor_height_above_crest_m, updated_at=excluded.updated_at
            """,
            (node_id, p.a, p.b, p.H0_m, p.sensor_height_above_crest_m),
        )
        self._conn.commit()

    # --- Telemetry ingest ---
    def upsert_telemetry(self, rec: Dict[str, Any]) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO telemetry(node_id, ts, dist_m, H_m, H_eff, Q_m3s, dH_10m, dQ_10m, rain_bin, batt_v, flags)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rec["node_id"], rec["ts"], rec.get("dist_m"), rec.get("H_m"), rec.get("H_eff"),
                rec.get("Q_m3s"), rec.get("dH_10m"), rec.get("dQ_10m"), rec.get("rain_bin"),
                rec.get("batt_v"), rec.get("flags"),
            ),
        )
        # device last seen
        cur.execute(
            """
            INSERT INTO devices(node_id, last_seen, batt_v, status)
            VALUES(?,?,?,?)
            ON CONFLICT(node_id) DO UPDATE SET last_seen=excluded.last_seen, batt_v=excluded.batt_v, status=excluded.status
            """,
            (rec["node_id"], rec["ts"], rec.get("batt_v"), "online"),
        )
        self._conn.commit()

    def latest_telemetry(self, node_id: str, limit: int = 200) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT ts, dist_m, H_m, H_eff, Q_m3s, dH_10m, dQ_10m, rain_bin, batt_v, flags FROM telemetry WHERE node_id=? ORDER BY ts DESC LIMIT ?",
            (node_id, limit),
        ).fetchall()
        cols = ["ts","dist_m","H_m","H_eff","Q_m3s","dH_10m","dQ_10m","rain_bin","batt_v","flags"]
        return [dict(zip(cols, r)) for r in rows][::-1]

    def value_10m_ago(self, node_id: str, ts_iso: str) -> Optional[dict[str, Any]]:
        try:
            ts = datetime.fromisoformat(ts_iso)
        except ValueError:
            return None
        ts_ago = (ts - timedelta(minutes=10)).isoformat()
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT H_m, Q_m3s FROM telemetry WHERE node_id=? AND ts<=? ORDER BY ts DESC LIMIT 1",
            (node_id, ts_ago),
        ).fetchone()
        if row:
            return {"H_m": row[0], "Q_m3s": row[1]}
        return None

    # --- Forecast ---
    def upsert_forecast(self, ts_run: str, horizon_h: int, node_id: str, prob_flood: float, wl_peak_cm: float, ci_low: float, ci_high: float) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO forecast(ts_run, horizon_h, node_id, prob_flood, wl_peak_cm, ci_low, ci_high)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(ts_run, horizon_h, node_id) DO UPDATE SET prob_flood=excluded.prob_flood, wl_peak_cm=excluded.wl_peak_cm, ci_low=excluded.ci_low, ci_high=excluded.ci_high
            """,
            (ts_run, horizon_h, node_id, prob_flood, wl_peak_cm, ci_low, ci_high),
        )
        self._conn.commit()

    def get_forecasts(self, node_id: str) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT ts_run, horizon_h, prob_flood, wl_peak_cm, ci_low, ci_high FROM forecast WHERE node_id=? ORDER BY ts_run DESC, horizon_h",
            (node_id,),
        ).fetchall()
        cols = ["ts_run","horizon_h","prob_flood","wl_peak_cm","ci_low","ci_high"]
        return [dict(zip(cols, r)) for r in rows]

    # --- Alerts ---
    def insert_alert(self, alert_id: str, ts: str, node_id: str, level: str, horizon_h: int, reason: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO alerts(alert_id, ts, node_id, level, horizon_h, reason) VALUES(?,?,?,?,?,?)",
            (alert_id, ts, node_id, level, horizon_h, reason),
        )
        self._conn.commit()

    def latest_alerts(self, limit: int = 5) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT alert_id, ts, node_id, level, horizon_h, reason FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        cols = ["alert_id","ts","node_id","level","horizon_h","reason"]
        return [dict(zip(cols, r)) for r in rows]
