from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


class FloodRiskModel:
    def __init__(self, threshold_mm: float = 50.0):
        self.threshold_mm = float(threshold_mm)
        self.clf = LogisticRegression(class_weight="balanced", max_iter=200)
        self._trained = False

    def set_threshold(self, threshold_mm: float) -> None:
        self.threshold_mm = float(threshold_mm)
        # retrain with new label rule
        self.train_bootstrap()

    def train_bootstrap(self, n_samples: int = 2000, noise: float = 6.0) -> None:
        # Synthetic training: features [instant, trend, prob]
        rng = np.random.default_rng(42)
        instant = rng.gamma(shape=2.0, scale=10.0, size=n_samples)
        trend = rng.normal(loc=0.0, scale=noise, size=n_samples)
        prob = np.clip(instant / 200.0 + rng.normal(0, 0.05, size=n_samples), 0, 1)
        X = np.vstack([instant, trend, prob]).T
        y = (instant >= self.threshold_mm).astype(int)
        if len(np.unique(y)) < 2:
            thr = float(np.quantile(instant, 0.6))
            y = (instant >= thr).astype(int)
        self.clf.fit(X, y)
        self._trained = True

    def predict_proba(self, X: np.ndarray) -> float:
        if not self._trained:
            self.train_bootstrap()
        # handle NaNs: replace with column means based on simple imputation
        X2 = X.copy()
        if np.isnan(X2).any():
            col_means = np.nanmean(X2, axis=0)
            col_means = np.where(np.isnan(col_means), 0.0, col_means)
            inds = np.where(np.isnan(X2))
            X2[inds] = np.take(col_means, inds[1])
        p = self.clf.predict_proba(X2)[0, 1]
        return float(p)
