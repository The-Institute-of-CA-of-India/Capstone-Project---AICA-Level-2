"""Background threads so OCR, detection, redaction and verification never freeze the window."""
from __future__ import annotations

import logging
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from ..core.models import UserFacingError

log = logging.getLogger("mukhota.workers")


class TaskWorker(QThread):
    """Runs ``fn(progress)`` in a thread and reports progress, result or a friendly error."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task_name: str, fn: Callable[[Callable[[int, str], None]], Any], parent=None) -> None:
        super().__init__(parent)
        self.task_name = task_name
        self.fn = fn

    def _report(self, pct: int, msg: str = "") -> None:
        self.progress.emit(int(pct), msg)

    def run(self) -> None:  # noqa: D401 - Qt override
        try:
            result = self.fn(self._report)
        except UserFacingError as exc:
            log.warning("%s stopped with a user-facing error (%s)", self.task_name, type(exc.__cause__).__name__)
            self.failed.emit(str(exc))
        except MemoryError:
            log.exception("%s ran out of memory", self.task_name)
            self.failed.emit(f"Your computer ran out of memory while {self.task_name}. Try a smaller PDF or lower the DPI in Settings.")
        except Exception:
            log.exception("%s failed", self.task_name)
            self.failed.emit(
                f"Something went wrong while {self.task_name}. The details were saved to logs\\mukhota.log."
            )
        else:
            self.succeeded.emit(result)
