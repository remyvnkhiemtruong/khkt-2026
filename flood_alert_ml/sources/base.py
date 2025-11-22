from typing import Protocol, Dict, Any
from datetime import datetime


class BaseFetcher(Protocol):
    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        """Return {'timestamp': datetime, 'precip_mm_h': float|None, 'precip_prob': float|None, 'source': str, 'meta': dict}"""
