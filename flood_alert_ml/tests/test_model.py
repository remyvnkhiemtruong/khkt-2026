import numpy as np

from flood_alert_ml.model import FloodRiskModel


def test_model_predict():
    m = FloodRiskModel(50)
    X = np.array([[10, 0, 0.2]])
    p = m.predict_proba(X)
    assert 0.0 <= p <= 1.0


def test_model_threshold_update():
    m = FloodRiskModel(50)
    m.set_threshold(60)
    X = np.array([[70, 0, 0.5]])
    p = m.predict_proba(X)
    assert 0.0 <= p <= 1.0
