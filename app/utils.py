from __future__ import annotations

"""Utilities: logging setup, time helpers, and small helpers.

Avoid importing Qt here so tests can import utilities without GUI deps.
"""

import base64
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


TZ_PLUS7 = timezone(timedelta(hours=7))


def now_iso_local() -> str:
    return datetime.now(TZ_PLUS7).isoformat()


def ensure_logo(path: Path) -> None:
    """Ensure a tiny placeholder PNG exists at path.

    Writes a 1x1 transparent PNG from embedded base64 if file is missing.
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tiny_png_b64 = (
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9bOqE/0AAAAASUVORK5CYII="
    )
    path.write_bytes(base64.b64decode(tiny_png_b64))


def safe_float(x: Any) -> float | None:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None
