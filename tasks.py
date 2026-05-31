"""Headless task-execution port.

The core schedules background work (preview / compression) through this module
instead of creating threads directly, so the execution strategy is swappable
without touching the model:

- **default**: one daemon thread per task — the current Tkinter-app behaviour;
- a managed thread/process pool later in the core service / backend;
- a synchronous runner in tests for determinism.

Synchronization primitives (``threading.Lock`` / ``threading.Event``) stay in the
model — they are plain, portable Python concurrency, not a GUI concern. This port
only owns *how a unit of work is started*.
"""

import threading
from typing import Callable, Optional, Protocol, runtime_checkable


@runtime_checkable
class Executor(Protocol):
    def submit(self, fn: Callable[[], None]) -> None: ...


class _ThreadExecutor:
    """Run each task on its own daemon thread (the historical behaviour)."""

    def submit(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=fn, daemon=True).start()


_executor: Executor = _ThreadExecutor()


def set_executor(executor: Optional[Executor]) -> None:
    """Install the active executor (``None`` resets to the default daemon-thread one)."""
    global _executor
    _executor = executor if executor is not None else _ThreadExecutor()


def submit(fn: Callable[[], None]) -> None:
    """Schedule ``fn`` to run as a background unit of work."""
    _executor.submit(fn)
