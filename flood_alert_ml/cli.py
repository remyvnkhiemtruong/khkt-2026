from __future__ import annotations

import argparse
import time

from .config import Preferences, DEFAULT_TZ
from .sources.open_meteo import OpenMeteoFetcher
from .sources.open_weather import OpenWeatherFetcher
from .sources.simulator import SimulatedFetcher
from .aggregator import WeatherAggregator
from .features import compute_trend_mm_h, make_feature_vector, make_feature_vector_h
from .model import FloodRiskModel
from .model_horizons import HorizonModels
from .logging_io import CSVLogger, ExcelLogger


def run_headless(lat: float, lon: float, interval: int, iterations: int = 1):
    prefs = Preferences(latitude=lat, longitude=lon)
    fetchers = [OpenMeteoFetcher(), OpenWeatherFetcher(), SimulatedFetcher()]
    agg = WeatherAggregator(fetchers)
    model = FloodRiskModel(prefs.threshold_mm_h)
    h_models = HorizonModels({3: 80, 6: 120, 9: 160, 12: 200, 24: 300})
    csv = CSVLogger()
    xlsx = ExcelLogger()
    history = []
    for i in range(max(1, iterations)):
        rows = agg.fetch_all_parallel(lat, lon, DEFAULT_TZ)
        A = agg.aggregate(rows)
        history.append(A["aggregated_precip_mm_h"])
        history[:] = history[-3:]
        trend = compute_trend_mm_h(history, 3)
        p = model.predict_proba(make_feature_vector(A["aggregated_precip_mm_h"], trend, None))
        print(f"Now={A['aggregated_precip_mm_h']:.1f} mm/h P={p:.2f}")
        if i + 1 < iterations and interval > 0:
            time.sleep(interval * 60)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=10.762622)
    ap.add_argument("--lon", type=float, default=106.660172)
    ap.add_argument("--interval", type=int, default=5)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--iterations", type=int, default=1)
    args = ap.parse_args(argv)
    run_headless(args.lat, args.lon, args.interval, args.iterations)


if __name__ == "__main__":
    main()
