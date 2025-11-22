from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import numpy as np

from .sources.base import BaseFetcher
from .utils import median_safe, std_safe


class WeatherAggregator:
    def __init__(self, fetchers: List["BaseFetcher"]):
        self.fetchers = fetchers

    def fetch_all_parallel(self, lat: float, lon: float, tz: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=len(self.fetchers) or 1, thread_name_prefix="fetch") as ex:
            futs = [ex.submit(f.fetch, lat, lon, tz) for f in self.fetchers]
            for fu in as_completed(futs):
                try:
                    rows.append(fu.result())
                except Exception as e:
                    rows.append({
                        "timestamp": None,
                        "precip_mm_h": None,
                        "precip_prob": None,
                        "source": "unknown",
                        "series": [],
                        "meta": {"error": str(e)},
                    })
        return rows

    def aggregate(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        vals = []
        notes = []
        for r in rows:
            v = r.get("precip_mm_h")
            if v is None:
                continue
            if v < 0:
                v = 0.0
                notes.append("Negative clamped")
            if v > 200.0:
                notes.append("Outlier dropped")
                continue
            vals.append(v)

        agg = median_safe(vals)
        sources_available = len(vals)
        degraded = sources_available <= 1
        if agg is None:
            agg = 0.0
            degraded = True
        disp = std_safe(vals) if len(vals) > 1 else 0.0
        # map dispersion to consensus score 0..1 (lower std -> higher)
        consensus_score = float(np.clip(1.0 - disp / 50.0, 0.0, 1.0))
        return {
            "aggregated_precip_mm_h": float(agg),
            "sources_available": sources_available,
            "consensus_score": consensus_score,
            "degraded": degraded,
            "notes": "; ".join(notes),
        }
