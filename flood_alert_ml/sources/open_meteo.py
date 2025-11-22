from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from ..utils import ShortCache, backoff_delays, utc_now


class OpenMeteoFetcher:
    BASE = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, cache: Optional[ShortCache] = None, timeout_s: int = 8):
        self.cache = cache or ShortCache(ttl_s=90)
        self.timeout_s = timeout_s

    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        url = self.BASE
        params = {
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "hourly": "precipitation,precipitation_probability,rain",
            "timezone": tz,
        }
        meta: Dict[str, Any] = {"http_status": None, "latency_ms": None, "raw": None, "error": None}
        start = time.time()
        key = f"open_meteo:{params['latitude']},{params['longitude']}"
        headers = self.cache.get_headers(key)
        payload = None
        for delay in backoff_delays(attempts=3):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=self.timeout_s)
                meta["http_status"] = resp.status_code
                if resp.status_code == 304:
                    payload = self.cache.get_cached_payload(key)
                    break
                resp.raise_for_status()
                payload = resp.json()
                self.cache.update(key, resp.headers, payload)
                break
            except Exception as e:
                meta["error"] = str(e)
                time.sleep(delay)
        meta["latency_ms"] = round((time.time() - start) * 1000, 2)

        ts = utc_now()
        precip = None
        prob = None
        series = []
        try:
            if payload:
                meta["raw"] = {"_": "omitted"}
                hours = payload.get("hourly", {})
                times = hours.get("time", [])
                precips = hours.get("precipitation", [])
                probs = hours.get("precipitation_probability", [])
                # choose last completed hour
                if precips:
                    precip = float(precips[0]) if isinstance(precips, (list, tuple)) else None
                    # set now as first if API returns starting from now; safer use last element
                    precip = float(precips[-1])
                    series = [float(x) for x in precips[:24]]
                if probs:
                    # Open-Meteo returns precipitation_probability in percent (0..100)
                    # Normalize to 0..1 for internal consistency
                    try:
                        prob = float(probs[-1]) / 100.0
                    except Exception:
                        prob = None
        except Exception as e:
            meta["error"] = (meta.get("error") or "") + f"; parse:{e}"

        return {
            "timestamp": ts,
            "precip_mm_h": precip,
            "precip_prob": prob,
            "source": "open_meteo",
            "series": series,
            "meta": meta,
        }
