from __future__ import annotations

"""HTTP ingest server using FastAPI.

Provides POST /ingest to accept telemetry payloads.
"""

import logging
import threading
from typing import Any, Dict

from fastapi import FastAPI, Request
import uvicorn

from ..storage.db import Database
from .telemetry_schema import validate_payload, process_payload


log = logging.getLogger(__name__)


class HTTPIngestServer:
    def __init__(self, db: Database, host: str = "0.0.0.0", port: int = 8088):
        self.db = db
        self.host = host
        self.port = port
        self.app = FastAPI()
        self._server_thread: threading.Thread | None = None
        self._configure_routes()

    def _configure_routes(self) -> None:
        @self.app.post("/ingest")
        async def ingest(request: Request) -> Dict[str, Any]:  # type: ignore
            try:
                payload = await request.json()
                node_id, ts_iso, dist_m, rain_bin, batt_v, meta = validate_payload(payload)
                rec = process_payload(self.db, node_id, ts_iso, dist_m, rain_bin, batt_v, meta)
                return {"ok": True, "stored": rec}
            except Exception as e:
                log.exception("ingest failed")
                return {"ok": False, "error": str(e)}

    def start_in_background(self) -> None:
        def _run() -> None:
            try:
                uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")
            except Exception:
                log.exception("uvicorn failed")

        if self._server_thread and self._server_thread.is_alive():
            return
        self._server_thread = threading.Thread(target=_run, name="HTTPIngest", daemon=True)
        self._server_thread.start()
