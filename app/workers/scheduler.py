from __future__ import annotations

"""Qt-based scheduler using QTimer ticks for UI refresh, model runs, APIs, maintenance."""

import logging
from typing import Callable
from PyQt6.QtCore import QObject, QTimer


log = logging.getLogger(__name__)


class Scheduler(QObject):
    def __init__(self, on_ui_tick: Callable[[], None], on_model_tick: Callable[[], None], on_api_tick: Callable[[], None], on_maintenance_tick: Callable[[], None]):
        super().__init__()
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(on_ui_tick)
        self.ui_timer.start(1000)  # 1s

        self.model_timer = QTimer(self)
        self.model_timer.timeout.connect(on_model_tick)
        self.model_timer.start(10 * 60 * 1000)  # 10 minutes

        self.api_timer = QTimer(self)
        self.api_timer.timeout.connect(on_api_tick)
        self.api_timer.start(45 * 60 * 1000)  # 45 minutes

        self.maint_timer = QTimer(self)
        self.maint_timer.timeout.connect(on_maintenance_tick)
        self.maint_timer.start(24 * 60 * 60 * 1000)  # daily
