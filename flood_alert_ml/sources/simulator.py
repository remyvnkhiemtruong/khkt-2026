from __future__ import annotations

import random
from typing import Any, Dict

from ..utils import utc_now


class SimulatedFetcher:
    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self.state = 10.0

    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        # random walk bounded [0, 120]
        delta = self.rng.uniform(-5.0, 5.0)
        self.state = max(0.0, min(120.0, self.state + delta))
        series = []
        s = self.state
        for _ in range(24):
            s = max(0.0, min(120.0, s + self.rng.uniform(-4.0, 4.0)))
            series.append(round(s, 2))
        return {
            "timestamp": utc_now(),
            "precip_mm_h": round(self.state, 2),
            "precip_prob": None,
            "source": "simulator",
            "series": series,
            "meta": {"http_status": None, "latency_ms": 0.0, "raw": None, "error": None},
        }
