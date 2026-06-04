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


# --- UI-thread dispatch ----------------------------------------------------
# Some callbacks (e.g. an import-finished handler) must run on the GUI's main
# thread. A headless backend has no such thread, so the default runs ``fn``
# inline. The Tk app registers a dispatcher that marshals onto the Tk loop.

_ui_dispatcher: Optional[Callable[[Callable[[], None]], None]] = None


def set_ui_dispatcher(dispatcher: Optional[Callable[[Callable[[], None]], None]]) -> None:
    """Install the callback that runs a function on the UI/main thread."""
    global _ui_dispatcher
    _ui_dispatcher = dispatcher


def run_on_ui_thread(fn: Callable[[], None]) -> None:
    """Run ``fn`` on the UI/main thread if one is registered, else inline."""
    if _ui_dispatcher is not None:
        _ui_dispatcher(fn)
    else:
        fn()
