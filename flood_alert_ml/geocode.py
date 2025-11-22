from __future__ import annotations

from typing import Tuple, Optional, Dict

import requests


class GeoCoder:
    def __init__(self):
        self.cache: Dict[str, str] = {}

    def _reverse_nominatim(self, lat: float, lon: float, timeout_s: int) -> Optional[str]:
        try:
            headers = {"User-Agent": "FloodAlertML/0.1 (+https://example.local)"}
            r = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": f"{lat:.6f}",
                    "lon": f"{lon:.6f}",
                    "format": "jsonv2",
                    "zoom": 18,
                    "addressdetails": 1,
                },
                headers=headers,
                timeout=timeout_s,
            )
            r.raise_for_status()
            j = r.json()
            addr = j.get("address", {})
            parts = [
                addr.get("neighbourhood") or addr.get("suburb"),
                addr.get("city_district") or addr.get("district"),
                addr.get("city") or addr.get("town") or addr.get("village"),
                addr.get("state"),
                addr.get("country"),
            ]
            label = ", ".join([p for p in parts if p])
            return label or j.get("display_name")
        except Exception:
            return None

    def _reverse_open_meteo(self, lat: float, lon: float, timeout_s: int) -> Optional[str]:
        try:
            r = requests.get(
                "https://geocoding-api.open-meteo.com/v1/reverse",
                params={"latitude": round(lat, 5), "longitude": round(lon, 5)},
                timeout=timeout_s,
            )
            r.raise_for_status()
            j = r.json()
            results = j.get("results") or []
            if results:
                res = results[0]
                comps = [res.get(k) for k in ("admin2", "admin1", "country") if res.get(k)]
                return ", ".join(comps) or res.get("name")
        except Exception:
            return None
        return None

    def reverse(self, lat: float, lon: float, timeout_s: int = 6) -> str:
        key = f"{lat:.5f},{lon:.5f}"
        if key in self.cache:
            return self.cache[key]
        label = self._reverse_nominatim(lat, lon, timeout_s) or self._reverse_open_meteo(lat, lon, timeout_s)
        label = label or key
        self.cache[key] = label
        return label
