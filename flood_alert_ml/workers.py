from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool


class WorkerSignals(QObject):
    success = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(float)


class FuncRunnable(QRunnable):
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.success.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))


class ThreadPool:
    def __init__(self, max_workers: int = 8):
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(max_workers)

    def submit(self, fn: Callable, *args, **kwargs) -> WorkerSignals:
        r = FuncRunnable(fn, *args, **kwargs)
        self.pool.start(r)
        return r.signals
