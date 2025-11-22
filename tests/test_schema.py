from __future__ import annotations

from app.ingest.telemetry_schema import validate_payload


def test_validate_payload_ok():
    sample = {
        "ts": "2025-11-03T09:15:00+07:00",
        "node_id": "CM-01",
        "s": {"dist_m": 0.83, "rain_bin": 1, "batt_v": 4.92},
        "meta": {"sensor_height_above_crest_m": 0.95},
        "ver": 2,
    }
    node_id, ts, dist, rain, batt, meta = validate_payload(sample)
    assert node_id == "CM-01" and dist == 0.83 and rain == 1 and batt == 4.92
