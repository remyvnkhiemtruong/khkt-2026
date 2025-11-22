from __future__ import annotations

from collections import deque
from typing import List, Dict, Optional

import numpy as np


def compute_trend_mm_h(history: "deque[float]", k: int = 3) -> float:
    arr = list(history)[-k:]
    if len(arr) < 2:
        return 0.0
    return float(arr[-1] - arr[0]) / max(1, len(arr) - 1)


def build_horizon_windows(hourly: list[float], hours: int) -> dict:
    # window [0..hours)
    win = hourly[: max(0, hours)]
    total = float(np.nansum(win)) if win else 0.0
    max_int = float(np.nanmax(win)) if win else 0.0
    return {"total": total, "max": max_int}


def rolling_sums(hourly: list[float], windows: list[int]) -> dict:
    out = {}
    for h in windows:
        out[str(h)] = float(np.nansum(hourly[:h])) if hourly else 0.0
    return out


def make_feature_vector(instant_agg: float, trend: float, prob_opt: float | None) -> np.ndarray:
    p = np.nan if prob_opt is None else float(prob_opt)
    return np.array([[float(instant_agg), float(trend), p]], dtype=float)


def make_feature_vector_h(agg_total: float, agg_max: float, mean_prob: float | None) -> np.ndarray:
    p = np.nan if mean_prob is None else float(mean_prob)
    return np.array([[float(agg_total), float(agg_max), p]], dtype=float)
