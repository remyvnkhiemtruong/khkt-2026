from __future__ import annotations

"""H–Q computation utilities.

Q = a * (H_eff ** b), H_eff = max(0, H - H0)
"""

from dataclasses import dataclass
from typing import Iterable, Tuple
import math


def compute_h_q(H_eff: float | None, a: float, b: float) -> float | None:
    """Compute discharge Q from effective head H_eff.

    Returns None if H_eff is None.
    """
    if H_eff is None:
        return None
    if H_eff <= 0:
        return 0.0
    try:
        return float(a) * float(H_eff) ** float(b)
    except Exception:
        return None


@dataclass
class FitResult:
    a: float
    b: float
    H0_m: float
    r2: float
    rmse: float


def _r2_rmse(y_true, y_pred) -> Tuple[float, float]:
    import numpy as np

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    ss_res = float(np.nansum((y_true - y_pred) ** 2))
    ss_tot = float(np.nansum((y_true - float(np.nanmean(y_true))) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / max(1, np.count_nonzero(~np.isnan(y_true)))))
    return r2, rmse


def fit_hq_params(H_m: Iterable[float], Q_m3s: Iterable[float]) -> FitResult:
    """Fit H–Q curve parameters (a, b, H0) with optional SciPy.

    Fallback: grid search H0 in [0, 0.1] step 0.001, linear regression on log(H_eff) vs log(Q).
    """
    import numpy as np

    H = np.asarray(list(H_m), dtype=float)
    Q = np.asarray(list(Q_m3s), dtype=float)
    mask = np.isfinite(H) & np.isfinite(Q) & (Q > 0)
    H = H[mask]
    Q = Q[mask]
    if H.size < 5:
        return FitResult(a=1.0, b=1.5, H0_m=0.0, r2=0.0, rmse=float("inf"))

    # Try SciPy curve_fit first
    try:
        from scipy.optimize import curve_fit  # type: ignore

        def model(Hm, a, b, H0):
            He = np.maximum(0.0, Hm - H0)
            return a * np.power(He, b)

        popt, _ = curve_fit(model, H, Q, p0=(1.0, 1.5, 0.0), maxfev=20000)
        a, b, H0 = [float(x) for x in popt]
        y_pred = model(H, a, b, H0)
        r2, rmse = _r2_rmse(Q, y_pred)
        return FitResult(a=a, b=b, H0_m=H0, r2=r2, rmse=rmse)
    except Exception:
        pass

    # Fallback grid search on H0, then linear regression in log space
    best = FitResult(a=1.0, b=1.5, H0_m=0.0, r2=0.0, rmse=float("inf"))
    H0_grid = np.arange(0.0, 0.1001, 0.001)
    for H0 in H0_grid:
        He = np.maximum(0.0, H - H0)
        m = He > 0
        if np.count_nonzero(m) < 5:
            continue
        X = np.log(He[m])
        y = np.log(Q[m])
        # linear regression y = log(a) + b * X
        n = X.size
        x_mean = float(np.mean(X))
        y_mean = float(np.mean(y))
        Sxy = float(np.sum((X - x_mean) * (y - y_mean)))
        Sxx = float(np.sum((X - x_mean) ** 2))
        if Sxx <= 0:
            continue
        b = Sxy / Sxx
        loga = y_mean - b * x_mean
        a = float(np.exp(loga))
        y_pred = a * np.exp(b * X)
        r2, rmse = _r2_rmse(y, y_pred)
        if r2 > best.r2:
            best = FitResult(a=a, b=float(b), H0_m=float(H0), r2=float(r2), rmse=float(rmse))
    return best
