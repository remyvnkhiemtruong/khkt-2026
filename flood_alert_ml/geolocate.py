from __future__ import annotations

from typing import Optional, Tuple

import json
import time

import requests


def _windows_location(timeout_s: int = 10) -> tuple[Optional[float], Optional[float]]:
    try:
        import winrt.windows.devices.geolocation as wgeo  # type: ignore

        async def _get():
            access = await wgeo.Geolocator.request_access_async()
            if access not in (wgeo.GeolocationAccessStatus.ALLOWED,):
                return None, None
            geolocator = wgeo.Geolocator()
            geolocator.desired_accuracy = wgeo.PositionAccuracy.HIGH
            pos = await geolocator.get_geoposition_async()
            c = pos.coordinate.point.position
            return float(c.latitude), float(c.longitude)

        # Run the coroutine with a simple loop via asyncio, respecting timeout
        import asyncio

        return asyncio.run(asyncio.wait_for(_get(), timeout=timeout_s))
    except Exception:
        return None, None


def _ip_location(timeout_s: int = 6) -> tuple[Optional[float], Optional[float]]:
    try:
        r = requests.get("https://ipapi.co/json/", timeout=timeout_s)
        r.raise_for_status()
        j = r.json()
        return float(j.get("latitude")), float(j.get("longitude"))
    except Exception:
        try:
            r = requests.get("https://ipinfo.io/json", timeout=timeout_s)
            r.raise_for_status()
            j = r.json()
            loc = (j.get("loc") or ",").split(",")
            return float(loc[0]), float(loc[1])
        except Exception:
            return None, None


def get_location(timeout_s: int = 10):
    """Return (lat: float|None, lon: float|None, source: str in {"windows","ip","unknown"})"""
    lat, lon = _windows_location(timeout_s)
    if lat is not None and lon is not None:
        return lat, lon, "windows"
    lat, lon = _ip_location(min(8, timeout_s))
    if lat is not None and lon is not None:
        return lat, lon, "ip"
    return None, None, "unknown"
