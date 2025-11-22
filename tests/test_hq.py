from __future__ import annotations

import math
from app.hq.hq_model import compute_h_q, fit_hq_params


def test_compute_hq_basic():
    assert compute_h_q(0.0, 2.0, 2.0) == 0.0
    assert math.isclose(compute_h_q(1.0, 2.0, 2.0) or 0.0, 2.0, rel_tol=1e-6)


def test_fit_fallback_matches_trend():
    # Synthetic: a=3.0, b=1.7, H0=0.02
    import numpy as np
    H = np.linspace(0.0, 0.2, 50)
    Q = 3.0 * np.maximum(0.0, H - 0.02) ** 1.7
    fit = fit_hq_params(H, Q)
    assert 2.0 < fit.a < 4.5
    assert 1.2 < fit.b < 2.2
    assert 0.0 <= fit.H0_m <= 0.05
