"""Headless progress port (no Tk, no GUI).

The core/model signals background-task start/finish through this module without
knowing anything about a GUI. By default nothing is wired up (a no-op), so the
domain code stays platform-agnostic and testable. The application installs a
reporter that forwards the signals to its status display (Tk today, the React
shell / core service later).

Part of the GUI<->core decoupling — replaces the model's direct dependency on
``status_display`` (which imports ``tkinter``).
"""

from typing import Optional, Protocol, runtime_checkable

from log_config import logger


@runtime_checkable
class ProgressReporter(Protocol):
    def task_started(self, name: str) -> None: ...
    def task_finished(self, name: str) -> None: ...


_reporter: Optional[ProgressReporter] = None


def set_reporter(reporter: Optional[ProgressReporter]) -> None:
    """Install (or clear, with ``None``) the active progress reporter."""
    global _reporter
    _reporter = reporter


def task_started(name: str) -> None:
    if _reporter is not None:
        try:
            _reporter.task_started(name)
        except Exception as e:
            logger.debug("Progress-Reporter (started) fehlgeschlagen: %s", e)


def task_finished(name: str) -> None:
    if _reporter is not None:
        try:
            _reporter.task_finished(name)
        except Exception as e:
            logger.debug("Progress-Reporter (finished) fehlgeschlagen: %s", e)
