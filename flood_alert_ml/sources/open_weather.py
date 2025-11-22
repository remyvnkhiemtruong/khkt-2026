from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from ..env import get_openweather_key
from ..utils import ShortCache, backoff_delays, utc_now
import numpy as np


class OpenWeatherFetcher:
    ONECALL = "https://api.openweathermap.org/data/2.5/onecall"
    WEATHER = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(self, cache: Optional[ShortCache] = None, timeout_s: int = 8):
        self.cache = cache or ShortCache(ttl_s=90)
        self.timeout_s = timeout_s

    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        api_key = get_openweather_key()
        meta: Dict[str, Any] = {"http_status": None, "latency_ms": None, "raw": None, "error": None}
        ts = utc_now()
        if not api_key:
            meta["error"] = "Missing OPENWEATHER_API_KEY"
            return {"timestamp": ts, "precip_mm_h": None, "precip_prob": None, "source": "openweather", "series": [], "meta": meta}

        # Try current weather rain.1h
        start = time.time()
        try:
            params = {"lat": round(lat, 5), "lon": round(lon, 5), "appid": api_key, "units": "metric"}
            key = f"owm:weather:{params['lat']},{params['lon']}"
            headers = self.cache.get_headers(key)
            payload = None
            for delay in backoff_delays(attempts=3):
                try:
                    r = requests.get(self.WEATHER, params=params, headers=headers, timeout=self.timeout_s)
                    meta["http_status"] = r.status_code
                    if r.status_code == 304:
                        payload = self.cache.get_cached_payload(key)
                        break
                    r.raise_for_status()
                    payload = r.json()
                    self.cache.update(key, r.headers, payload)
                    break
                except Exception as e:
                    meta["error"] = str(e)
                    time.sleep(delay)
            precip_now = None
            if payload:
                meta["raw"] = {"_": "omitted"}
                rain = payload.get("rain") or {}
                v = rain.get("1h")
                if v is not None:
                    precip_now = float(v)
        except Exception as e:
            meta["error"] = (meta.get("error") or "") + f"; weather:{e}"

        # Get hourly to derive prob and series
        series = []
        prob = None
        try:
            params = {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "appid": api_key,
                "units": "metric",
                "exclude": "minutely,daily,alerts",
            }
            key = f"owm:onecall:{params['lat']},{params['lon']}"
            headers = self.cache.get_headers(key)
            payload = None
            for delay in backoff_delays(attempts=3):
                try:
                    r = requests.get(self.ONECALL, params=params, headers=headers, timeout=self.timeout_s)
                    if r.status_code == 304:
                        payload = self.cache.get_cached_payload(key)
                        break
                    r.raise_for_status()
                    payload = r.json()
                    self.cache.update(key, r.headers, payload)
                    break
                except Exception as e:
                    meta["error"] = (meta.get("error") or "") + f"; onecall:{e}"
                    time.sleep(delay)

            if payload and (hourly := payload.get("hourly")):
                series = [float((h.get("rain") or {}).get("1h", 0.0)) for h in hourly[:24]]
                # OpenWeather 'pop' is already 0..1; keep as fraction
                pops = [float(h.get("pop", 0.0)) for h in hourly[:24]]
                prob = float(np.mean(pops)) if pops else None
                if precip_now is None and hourly:
                    precip_now = float((hourly[0].get("rain") or {}).get("1h", 0.0))
        except Exception as e:
            meta["error"] = (meta.get("error") or "") + f"; onecall-parse:{e}"

        meta["latency_ms"] = round((time.time() - start) * 1000, 2)
        return {
            "timestamp": ts,
            "precip_mm_h": precip_now,
            "precip_prob": prob,
            "source": "openweather",
            "series": series,
            "meta": meta,
        }
