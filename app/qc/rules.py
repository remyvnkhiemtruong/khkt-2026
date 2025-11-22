from __future__ import annotations

"""QC rules implementation.

Flags:
 - OUT_OF_RANGE_DIST: dist outside [0.05, 5.0]
 - NEG_H: H_m < -0.02
 - SPIKES_H: large |dH_10m| proxy (>= 0.15 m / 10m)
 - OUT_OF_RANGE_Q: Q negative or above configured max (use conservative 1000 m3/s default)

STUCK_H requires windowed evaluation; not implemented in this streaming single-sample context.
"""

from typing import Optional


def qc_flags(dist_m: Optional[float], H_m: Optional[float], dH_10m: Optional[float], Q_m3s: Optional[float], q_max: float = 1000.0) -> str:
    flags: list[str] = []
    if dist_m is not None and not (0.05 <= dist_m <= 5.0):
        flags.append("OUT_OF_RANGE_DIST")
    if H_m is not None and H_m < -0.02:
        flags.append("NEG_H")
    if dH_10m is not None and abs(dH_10m) >= 0.15:
        flags.append("SPIKES_H")
    if Q_m3s is not None and (Q_m3s < 0 or Q_m3s > q_max):
        flags.append("OUT_OF_RANGE_Q")
    return "|".join(flags)
