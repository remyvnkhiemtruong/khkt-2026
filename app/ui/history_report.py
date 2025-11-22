from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog

from ..storage.db import Database
from ..storage.logging_io import export_telemetry_csv, export_report_pdf


class HistoryReportTab(QWidget):
    def __init__(self, db: Database, node_id: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.node_id = node_id
        layout = QVBoxLayout(self)
        self.btn_csv = QPushButton("Export CSV")
        self.btn_pdf = QPushButton("Export PDF")
        layout.addWidget(self.btn_csv)
        layout.addWidget(self.btn_pdf)
        self.btn_csv.clicked.connect(self._on_csv)
        self.btn_pdf.clicked.connect(self._on_pdf)

    def _on_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "telemetry.csv", "CSV (*.csv)")
        if path:
            export_telemetry_csv(self.db, self.node_id, Path(path))

    def _on_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "report.pdf", "PDF (*.pdf)")
        if path:
            export_report_pdf(self.db, self.node_id, Path(path))
