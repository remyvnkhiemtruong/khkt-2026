from __future__ import annotations

import time
from typing import Any, Dict, Optional
import requests

try:
    import firebase_admin
    from firebase_admin import credentials, db
except Exception:  # pragma: no cover - optional dependency
    firebase_admin = None  # type: ignore
    credentials = None  # type: ignore
    db = None  # type: ignore

from ..utils import utc_now
from ..env import (
    get_firebase_db_url,
    get_firebase_web_api_key,
    get_firebase_service_account_path,
)
from ..firebase_auth import get_firebase_id_token


class FirebaseStationFetcher:
    """
    Lấy dữ liệu trực tiếp từ trạm quan trắc qua Firebase Realtime Database.

    Ghi chú:
    - Cần file service account JSON (service_account_key)
    - Cần cung cấp database_url dạng https://<project-id>.firebaseio.com hoặc từ biến môi trường FIREBASE_DB_URL
    """

    def __init__(
        self,
        station_id: str = "station_A",
        service_account_key: str = "firebase-service-account.json",
        database_url: Optional[str] = None,
        prefer_rest: bool = False,
    ):
        self.station_id = station_id
        self.source = f"station_{station_id}"
        self._db_root = None

        # Chỉ khởi tạo firebase_admin nếu có và không ép dùng REST
        if firebase_admin is None or prefer_rest:
            return

        try:
            # Cho phép cấu hình URL qua biến môi trường
            import os
            db_url = database_url or get_firebase_db_url()
            if not db_url:
                return
            # resolve service account path (priority: explicit arg then env then default)
            svc_path = service_account_key
            if not os.path.isfile(svc_path):
                env_path = get_firebase_service_account_path()
                if env_path and os.path.isfile(env_path):
                    svc_path = env_path
            if not os.path.isfile(svc_path):
                # leave uninitialized; will fallback REST
                return
            if not firebase_admin._apps:  # type: ignore[attr-defined]
                cred = credentials.Certificate(svc_path)  # type: ignore[call-arg]
                firebase_admin.initialize_app(cred, {  # type: ignore[call-arg]
                    "databaseURL": db_url,
                })
            self._db_root = db.reference("/")  # type: ignore[assignment]
        except Exception:
            self._db_root = None

    def fetch(self, lat: float, lon: float, tz: str) -> Dict[str, Any]:
        meta: Dict[str, Any] = {"http_status": None, "latency_ms": None, "raw": None, "error": None}
        ts = utc_now()
        start = time.time()

        # Fallback REST nếu admin SDK không khả dụng hoặc chưa init
        if firebase_admin is None or self._db_root is None:
            db_url = get_firebase_db_url()
            if not db_url:
                meta["error"] = "Missing FIREBASE_DB_URL"
                return self._format(ts, meta, None, None, [], None, None, None, None)
            id_token = None
            api_key = get_firebase_web_api_key()
            if api_key:
                id_token = get_firebase_id_token()
            try:
                base = db_url.rstrip('/')
                url = f"{base}/stations/{self.station_id}/live_data.json"
                params = {}
                if id_token:
                    params['auth'] = id_token
                r_start = time.time()
                resp = requests.get(url, params=params, timeout=10)
                meta['http_status'] = resp.status_code
                resp.raise_for_status()
                data = resp.json() if resp.text.strip() else {}
                meta['latency_ms'] = round((time.time() - r_start) * 1000, 2)
                if not data:
                    meta['error'] = 'Không tìm thấy dữ liệu trạm (REST)'
                    return self._format(ts, meta, None, None, [], None, None, None, None)
                meta['raw'] = {'_': 'omitted'}
                # Per user requirement: rainfall is fixed based on float switch
                float_active = bool(data.get('float_active', False))
                precip_mm_h = 100.0 if float_active else 0.0
                flow_lpm_raw = data.get('flow_lpm')
                try:
                    flow_lpm = float(flow_lpm_raw if flow_lpm_raw is not None else 0.0)
                except Exception:
                    flow_lpm = 0.0
                temp_raw = data.get('temperature')
                humidity_raw = data.get('humidity')
                try:
                    temp = float(temp_raw if temp_raw is not None else 0.0)
                except Exception:
                    temp = 0.0
                try:
                    humidity = float(humidity_raw if humidity_raw is not None else 0.0)
                except Exception:
                    humidity = 0.0
                return self._format(ts, meta, precip_mm_h, None, [], flow_lpm, float_active, temp, humidity)
            except Exception as e:
                meta['error'] = str(e)
                return self._format(ts, meta, None, None, [], None, None, None, None)

        try:
            path = f"stations/{self.station_id}/live_data"
            data = self._db_root.child(path).get()  # type: ignore[union-attr]
            meta["latency_ms"] = round((time.time() - start) * 1000, 2)

            if not data:
                meta["error"] = "Không tìm thấy dữ liệu trạm"
                return self._format(ts, meta, None, None, [], None, None, None, None)

            meta["raw"] = data

            # Per user requirement: rainfall is fixed based on float switch
            float_active = bool(data.get("float_active", False))
            precip_mm_h = 100.0 if float_active else 0.0

            flow_lpm = float(data.get("flow_lpm", 0))
            temp = float(data.get("temperature", 0))
            humidity = float(data.get("humidity", 0))

            return self._format(ts, meta, precip_mm_h, None, [], flow_lpm, float_active, temp, humidity)

        except Exception as e:
            meta["error"] = str(e)
            return self._format(ts, meta, None, None, [], None, None, None, None)

    @staticmethod
    def _calibrate_rain_sensor(analog_value: int) -> float:
        # Giả sử giá trị analog càng thấp -> càng ướt
        if analog_value < 1000:
            return 50.0  # Mưa lớn
        if analog_value < 2000:
            return 10.0  # Mưa vừa
        return 0.0  # Khô

    def _format(
        self,
        ts,
        meta,
        precip,
        prob,
        series,
        flow,
        float_level,
        temp,
        humidity,
    ) -> Dict[str, Any]:
        """Đóng gói dữ liệu trả về, thêm các trường phần cứng."""
        return {
            "timestamp": ts,
            "precip_mm_h": precip,
            "precip_prob": prob,
            "source": self.source,
            "series": series,
            "meta": meta,
            # Dữ liệu phần cứng riêng
            "flow_lpm": flow,
            "float_active": float_level,
            "temperature": temp,
            "humidity": humidity,
        }
