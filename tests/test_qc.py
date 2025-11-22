from __future__ import annotations

from app.qc.rules import qc_flags


def test_qc_out_of_range_and_neg():
    f = qc_flags(dist_m=10.0, H_m=-0.05, dH_10m=0.0, Q_m3s=0.0)
    assert "OUT_OF_RANGE_DIST" in f and "NEG_H" in f


def test_qc_spike_and_qmax():
    f = qc_flags(dist_m=0.5, H_m=0.1, dH_10m=0.2, Q_m3s=1500.0, q_max=1000.0)
    assert "SPIKES_H" in f and "OUT_OF_RANGE_Q" in f
