from typing import Dict, Any

from flood_alert_ml.aggregator import WeatherAggregator


class F:
    def __init__(self, v: float):
        self.v = v

    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        return {"timestamp": None, "precip_mm_h": self.v, "precip_prob": None, "source": "x", "series": [], "meta": {}}


def test_aggregate_median():
    agg = WeatherAggregator([F(10), F(40), F(20)])
    rows = agg.fetch_all_parallel(0, 0, "UTC")
    a = agg.aggregate(rows)
    assert a["aggregated_precip_mm_h"] == 20
    assert a["sources_available"] == 3
