from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QFileDialog

from ..hq.hq_calibration import import_csv_and_fit


class HQCalibrationDialog(QDialog):
    def __init__(self, on_apply, parent=None):
        super().__init__(parent)
        self.on_apply = on_apply
        self.setWindowTitle("H–Q Calibration")
        layout = QVBoxLayout(self)
        self.lbl = QLabel("Import CSV (H,Q) and fit a,b,H0")
        self.btn_import = QPushButton("Import CSV & Fit")
        self.btn_apply = QPushButton("Apply to Node")
        self.btn_apply.setEnabled(False)
        layout.addWidget(self.lbl)
        layout.addWidget(self.btn_import)
        layout.addWidget(self.btn_apply)
        self.btn_import.clicked.connect(self._on_import)
        self.btn_apply.clicked.connect(self._on_apply)
        self.fit = None

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", filter="CSV (*.csv)")
        if not path:
            return
        try:
            res = import_csv_and_fit(Path(path))
            self.fit = res.fit
            self.lbl.setText(f"Fit: a={self.fit.a:.3g}, b={self.fit.b:.3g}, H0={self.fit.H0_m:.3f} m | R2={self.fit.r2:.3f}, RMSE={self.fit.rmse:.3f}")
            self.btn_apply.setEnabled(True)
        except Exception as e:
            self.lbl.setText(f"Fit failed: {e}")

    def _on_apply(self) -> None:
        if self.fit and self.on_apply:
            self.on_apply(self.fit)
            self.accept()
