from __future__ import annotations

"""ModelService plugin interface and baseline implementation.

Loads scikit-learn LogisticRegression model if available; otherwise uses a heuristic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import logging

import numpy as np

try:
    import joblib  # type: ignore
except Exception:  # pragma: no cover
    joblib = None  # type: ignore


log = logging.getLogger(__name__)


@dataclass
class ModelService:
    model_dir: Path | None = None
    _clf: object | None = None

    def load(self, model_dir: str | Path | None) -> None:
        self.model_dir = Path(model_dir) if model_dir else None
        self._clf = None
        if self.model_dir and joblib:
            p = self.model_dir / "model.joblib"
            if p.exists():
                try:
                    self._clf = joblib.load(p)
                    log.info("Loaded ML model from %s", p)
                except Exception:
                    log.exception("Failed to load model; fallback to heuristic")

    def _heuristic_prob(self, H: float, dH_10m: float | None, rain_mmph_next1h: float | None) -> float:
        # Simple rule: increase probability with H (cm), delta H (m/10m), and rain
        H_cm = max(0.0, H) * 100.0
        dh = 0.0 if dH_10m is None else max(0.0, dH_10m) * 10.0  # scale
        rain = 0.0 if rain_mmph_next1h is None else rain_mmph_next1h / 10.0
        score = 0.003 * H_cm + 0.2 * dh + 0.1 * rain
        return float(max(0.0, min(1.0, score)))

    def predict(self, features: Dict, horizons: List[int]) -> Dict[int, Dict[str, float | tuple]]:
        """Predict for horizons in hours.

        features keys example: {"H_m": float, "dH_10m": float, "rain_next_hour": float}
        Returns dict[h] = {"prob_flood": float, "wl_peak_cm": float, "ci": (low, high)}
        """
        out: Dict[int, Dict[str, float | tuple]] = {}
        H = float(features.get("H_m", 0.0) or 0.0)
        dH_10m = features.get("dH_10m")
        rain1h = features.get("rain_next_hour")

        if self._clf is not None:
            # Build feature vector per horizon if needed; simple reuse
            X = []
            for _ in horizons:
                X.append([H, dH_10m or 0.0, rain1h or 0.0])
            X = np.asarray(X, dtype=float)
            try:
                probs = self._clf.predict_proba(X)[:, 1]
            except Exception:
                log.exception("Model predict failed; fallback to heuristic")
                probs = np.asarray([self._heuristic_prob(H, dH_10m, rain1h) for _ in horizons])
        else:
            probs = np.asarray([self._heuristic_prob(H, dH_10m, rain1h) for _ in horizons])

        for i, h in enumerate(horizons):
            prob = float(probs[i])
            wl_peak_cm = max(0.0, H * 100.0 + (dH_10m or 0.0) * 6.0 * 100.0)  # naive projection 1h ~ 6*10m
            ci = (max(0.0, wl_peak_cm - 5.0), wl_peak_cm + 5.0)
            out[h] = {"prob_flood": prob, "wl_peak_cm": wl_peak_cm, "ci": ci}
        return out
