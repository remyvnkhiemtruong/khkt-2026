from __future__ import annotations

import math
import os
import random
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    if v is None:
        return None
    return max(lo, min(hi, v))


def median_safe(values: Iterable[float]) -> Optional[float]:
    vals = [v for v in values if v is not None and not math.isnan(v)]
    if not vals:
        return None
    return float(np.median(vals))


def std_safe(values: Iterable[float]) -> float:
    vals = [v for v in values if v is not None and not math.isnan(v)]
    if len(vals) < 2:
        return 0.0
    return float(np.std(vals))


def backoff_delays(base: float = 0.5, factor: float = 2.0, attempts: int = 3, jitter: float = 0.2):
    d = base
    for _ in range(attempts):
        yield max(0.0, random.uniform(d * (1 - jitter), d * (1 + jitter)))
        d = min(d * factor, 30.0)


@contextmanager
def atomic_write(path: Path):
    tmp = path.with_suffix(path.suffix + ".tmp")
    yield tmp
    tmp.replace(path)


class ShortCache:
    """Simple short-lived cache for HTTP responses (ETag/Last-Modified)"""

    def __init__(self, ttl_s: int = 90):
        self.ttl_s = ttl_s
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_headers(self, key: str) -> Dict[str, str]:
        e = self._store.get(key)
        headers: Dict[str, str] = {}
        if e and time.time() - e.get("ts", 0) < self.ttl_s:
            if et := e.get("etag"):
                headers["If-None-Match"] = et
            if lm := e.get("last_modified"):
                headers["If-Modified-Since"] = lm
        return headers

    def update(self, key: str, response_headers: Dict[str, str], payload: Any) -> None:
        self._store[key] = {
            "ts": time.time(),
            "etag": response_headers.get("ETag") or response_headers.get("Etag"),
            "last_modified": response_headers.get("Last-Modified"),
            "payload": payload,
        }

    def get_cached_payload(self, key: str) -> Optional[Any]:
        e = self._store.get(key)
        if e and time.time() - e.get("ts", 0) < self.ttl_s:
            return e.get("payload")
        return None
