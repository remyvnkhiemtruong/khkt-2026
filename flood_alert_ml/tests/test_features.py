from collections import deque

import numpy as np

from flood_alert_ml.features import compute_trend_mm_h, build_horizon_windows, rolling_sums, make_feature_vector


def test_trend():
    d = deque([1, 2, 4], maxlen=3)
    assert compute_trend_mm_h(d, 3) == (4 - 1) / 2


def test_horizon_window():
    hourly = [1, 2, 3, 4]
    w = build_horizon_windows(hourly, 3)
    assert w["total"] == 6
    assert w["max"] == 3


def test_feature_vector_shape():
    X = make_feature_vector(10, 1, None)
    assert X.shape == (1, 3)
