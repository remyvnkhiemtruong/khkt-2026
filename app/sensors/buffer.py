from __future__ import annotations

"""Simple ring buffer and median/mean utilities for UI sparklines."""

from collections import deque
from typing import Iterable, Deque, Optional
import numpy as np


class RingBuffer:
    def __init__(self, maxlen: int = 3600):
        self.data: Deque[float] = deque(maxlen=maxlen)

    def append(self, x: float) -> None:
        self.data.append(float(x))

    def to_list(self) -> list[float]:
        return list(self.data)

    def mean(self) -> Optional[float]:
        if not self.data:
            return None
        return float(np.mean(self.to_list()))

    def median(self) -> Optional[float]:
        if not self.data:
            return None
        return float(np.median(self.to_list()))
