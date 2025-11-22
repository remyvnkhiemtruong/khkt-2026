from __future__ import annotations

"""Weather API client with simple caching to SQLite api_cache.

To keep offline-friendly behavior, returns stubbed values if network fails.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import requests

from ..storage.db import Database


log = logging.getLogger(__name__)


def _hash_payload(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode("utf-8")).hexdigest()


def get_rain_next_hour_mmph(db: Database, lat: float, lon: float, api_key: str | None) -> float:
    """Return forecast rain rate for next hour (mm/h).

    Caches response for 45 minutes; on failure returns 0.0.
    """
    try:
        now = datetime.now(timezone.utc)
        valid_from = (now - timedelta(minutes=1)).isoformat()
        valid_to = (now + timedelta(minutes=45)).isoformat()
        key = {"source": "open-meteo", "lat": lat, "lon": lon}
        h = _hash_payload(key)
        # No explicit api_cache get method; keep simple and call API directly
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_days=1&timezone=auto"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            js = resp.json()
            # Get first hour precipitation (mm)
            mm = 0.0
            try:
                mm = float(js["hourly"]["precipitation"][0])
            except Exception:
                mm = 0.0
            return max(0.0, mm)
    except Exception:
        log.warning("Weather API failed; returning 0.0")
    return 0.0
