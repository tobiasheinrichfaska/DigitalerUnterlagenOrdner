"""CPU fairness primitives for the background render/compression workers.

The point of this module is to be a *good neighbour* on a shared host (a Windows
Terminal Server / RDS where many users run the app at once): fill idle cores for a
lone user, but yield instantly the moment anyone else needs the CPU.

Three levers, all here and all individually testable (the OS calls are injected /
guarded so the logic runs on any platform):

* ``worker_count`` — a bounded, session-aware pool size. Caps lower in an RDP
  session so one user can't grab the whole box; overridable via ``BELEG_WORKERS``.
* ``set_current_thread_below_normal`` — drop a worker thread's priority so the OS
  preempts it for any interactive work (including other sessions' work).
* ``SystemCpuSampler`` — a delta-based whole-system CPU reading (``GetSystemTimes``,
  no extra dependency) so background prefetch backs off when the box is loaded.

Nothing here imports the model, the UI, or the render service.
"""

from __future__ import annotations

import os
import sys
import threading
from typing import Callable, Mapping, Optional

IS_WINDOWS = sys.platform == "win32"

# Windows constants
_SM_REMOTESESSION = 0x1000
_THREAD_PRIORITY_BELOW_NORMAL = -1

# pool caps — a console (local) session may use more cores than an RDP session,
# where we deliberately stay small so N concurrent users don't oversubscribe.
CAP_LOCAL = 4
CAP_REMOTE = 2


def is_remote_session(*, _force: Optional[bool] = None) -> bool:
    """True when the app runs inside an RDP / Terminal-Server session.

    ``_force`` is a test seam. Falls back to the ``SESSIONNAME`` env convention
    (``RDP-Tcp#…``) if the Win32 call is unavailable.
    """
    if _force is not None:
        return _force
    if IS_WINDOWS:
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetSystemMetrics(_SM_REMOTESESSION))
        except Exception:
            pass
    return os.environ.get("SESSIONNAME", "").upper().startswith("RDP-")


def worker_count(
    *,
    env: Mapping[str, str] = os.environ,
    cpu_count: Optional[int] = None,
    remote: Optional[bool] = None,
) -> int:
    """Number of background worker threads to use.

    ``BELEG_WORKERS`` (a positive int) overrides everything. Otherwise:
    ``clamp(1, cores - 1, cap)`` where the cap is smaller in an RDP session.
    Always at least 1 (so a single-core box still makes progress).
    """
    override = env.get("BELEG_WORKERS", "").strip()
    if override.isdigit() and int(override) >= 1:
        return int(override)
    cores = cpu_count if cpu_count is not None else (os.cpu_count() or 2)
    cap = CAP_REMOTE if (is_remote_session() if remote is None else remote) else CAP_LOCAL
    return max(1, min(cap, cores - 1))


def set_current_thread_below_normal() -> None:
    """Lower the calling thread's priority so the OS preempts it for interactive
    work. No-op (and never raises) off Windows or if the call fails — used as a
    ``ThreadPoolExecutor(initializer=…)``."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetCurrentThread()  # pseudo-handle, no close
        ctypes.windll.kernel32.SetThreadPriority(handle, _THREAD_PRIORITY_BELOW_NORMAL)
    except Exception:
        pass


def _filetime(ft) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


class SystemCpuSampler:
    """Whole-system CPU busy fraction (0..1) over the interval between calls.

    Delta-based against ``GetSystemTimes`` (kernel time *includes* idle, so
    busy = (kernel + user) - idle). The first call has no baseline → returns 0.0.
    Thread-safe; the reader is injected so tests can drive it deterministically.
    """

    def __init__(self, reader: Optional[Callable[[], Optional[tuple]]] = None):
        self._reader = reader or self._read_system_times
        self._prev: Optional[tuple] = None
        self._lock = threading.Lock()

    @staticmethod
    def _read_system_times() -> Optional[tuple]:
        if not IS_WINDOWS:
            return None
        try:
            import ctypes
            from ctypes import wintypes
            idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            ok = ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
            if not ok:
                return None
            return _filetime(idle), _filetime(kernel), _filetime(user)
        except Exception:
            return None

    def load(self) -> float:
        sample = self._reader()
        if sample is None:
            return 0.0  # unknown → assume idle (don't throttle blindly)
        idle_t, kernel_t, user_t = sample
        with self._lock:
            prev = self._prev
            self._prev = sample
        if prev is None:
            return 0.0
        d_idle = idle_t - prev[0]
        d_total = (kernel_t - prev[1]) + (user_t - prev[2])  # kernel already counts idle
        if d_total <= 0:
            return 0.0
        busy = d_total - d_idle
        return max(0.0, min(1.0, busy / d_total))


# process-wide default sampler (the render service uses this unless injected)
default_sampler = SystemCpuSampler()
