from __future__ import annotations

from typing import Dict

import numpy as np
from sklearn.linear_model import LogisticRegression


class HorizonModels:
    def __init__(self, thresholds: Dict[int, float]):
        self.thresholds = thresholds
        self.models: Dict[int, LogisticRegression] = {}
        self._train_all()

    def update_threshold(self, horizon: int, value: float) -> None:
        self.thresholds[horizon] = float(value)
        self._train(horizon)

    def _train_all(self) -> None:
        for h, thr in self.thresholds.items():
            self._train(h)

    def _train(self, horizon: int) -> None:
        n = 3000
        rng = np.random.default_rng(123 + horizon)
        total = rng.gamma(shape=2.0, scale=20.0, size=n)
        max_int = rng.gamma(shape=2.0, scale=10.0, size=n)
        prob = np.clip(total / (horizon * 50.0) + rng.normal(0, 0.05, n), 0, 1)
        X = np.vstack([total, max_int, prob]).T
        thr = self.thresholds[horizon]
        y = (total >= thr).astype(int)
        # Ensure both classes exist; fallback to a quantile-based threshold
        if len(np.unique(y)) < 2:
            thr = float(np.quantile(total, 0.6))
            y = (total >= thr).astype(int)
        clf = LogisticRegression(class_weight="balanced", max_iter=200)
        clf.fit(X, y)
        self.models[horizon] = clf

    def predict_proba(self, horizon: int, X: np.ndarray) -> float:
        if horizon not in self.models:
            self._train(horizon)
        clf = self.models[horizon]
        X2 = X.copy()
        if np.isnan(X2).any():
            col_means = np.nanmean(X2, axis=0)
            col_means = np.where(np.isnan(col_means), 0.0, col_means)
            inds = np.where(np.isnan(X2))
            X2[inds] = np.take(col_means, inds[1])
        p = clf.predict_proba(X2)[0, 1]
        return float(p)
