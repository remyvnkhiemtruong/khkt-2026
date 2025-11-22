from __future__ import annotations

"""CSV import and calibration helpers for H–Q fitting."""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
import logging
import pandas as pd

from .hq_model import fit_hq_params, FitResult


log = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    fit: FitResult
    n: int


def import_csv_and_fit(path: Path) -> CalibrationResult:
    """Load CSV with columns H,Q (case-insensitive) and fit parameters.

    Returns CalibrationResult with fit and count.
    """
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    if 'h' not in cols or 'q' not in cols:
        raise ValueError("CSV must contain columns H and Q")
    H = df[cols['h']].astype(float).tolist()
    Q = df[cols['q']].astype(float).tolist()
    fit = fit_hq_params(H, Q)
    return CalibrationResult(fit=fit, n=len(H))
