from __future__ import annotations

"""Export helpers: CSV and simple PDF using reportlab.

This module reads from Database and writes export files.
"""

import io
import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .db import Database


log = logging.getLogger(__name__)


def export_telemetry_csv(db: Database, node_id: str, path: Path) -> None:
    rows = db.latest_telemetry(node_id=node_id, limit=10000)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def export_report_pdf(db: Database, node_id: str, path: Path) -> None:
    rows = db.latest_telemetry(node_id=node_id, limit=200)
    alerts = db.latest_alerts(limit=5)

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list = []

    elements.append(Paragraph("Flood Alert Report", styles["Title"]))
    elements.append(Paragraph(f"Node: {node_id}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    if alerts:
        elements.append(Paragraph("Latest Alerts", styles["Heading2"]))
        data = [["ts", "level", "horizon_h", "reason"]] + [[a["ts"], a["level"], a["horizon_h"], a["reason"]] for a in alerts]
        tbl = Table(data)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.lightgrey),
            ('GRID',(0,0),(-1,-1), 0.5, colors.grey)
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 12))

    if rows:
        elements.append(Paragraph("Recent Telemetry (last 200)", styles["Heading2"]))
        header = list(rows[0].keys())
        table_data = [header] + [[str(r.get(k, "")) for k in header] for r in rows[:30]]  # cap rows for brevity
        tbl = Table(table_data)
        tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), colors.lightgrey),
            ('GRID',(0,0),(-1,-1), 0.5, colors.grey)
        ]))
        elements.append(tbl)

    doc.build(elements)
