"""Logging seam of the ``datev`` package (keeps the package free of host-app imports).

``logger`` is a plain stdlib logger named ``"datev"``. ``diag`` is an always-on diagnostic
breadcrumb hook: a no-op by default; a host application injects its own sink with
``set_diag(fn)`` (``fn(msg: str) -> None``)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("datev")

_diag_hook: Optional[Callable[[str], None]] = None


def set_diag(fn: Optional[Callable[[str], None]]) -> None:
    """Install (or, with ``None``, remove) the diagnostic sink."""
    global _diag_hook
    _diag_hook = fn


def diag(msg: str) -> None:
    """Forward ``msg`` to the injected sink; never raises, no-op without a sink."""
    hook = _diag_hook
    if hook is None:
        return
    try:
        hook(msg)
    except Exception:  # a diagnostic must never break the operation it describes
        logger.debug("diag hook failed", exc_info=True)
