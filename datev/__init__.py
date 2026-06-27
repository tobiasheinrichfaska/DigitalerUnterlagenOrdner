"""DATEVconnect Dokumentenablage (DMS v2) connector for BelegTool.

A small, UI-free, injected-transport client + orchestration (``DatevService``) so we can
read / create / write back documents in the local DATEVconnect API. It is consumed by
``CoreApi`` in DATEV mode (the React/pywebview front end) — the package itself is headless
and has no UI. The standalone ``probe_gui.py`` (Tkinter) is research-only tooling, not
shipped. See ``docs/datev-integration-design.md`` and ``docs/datev-probe.md``.

The program type (``DokAB`` / ``DokAbRev`` / ``DMS``, from ``GET /info``) decides whether
a file exchange is overwritten (DokAB) or kept as a revision (DokAbRev/DMS).
"""

from .types import (
    DatevConfig,
    DatevError,
    DatevAuthError,
    DatevLicenseError,
    program_keeps_revisions,
)
from .client import DatevConnectClient

__all__ = [
    "DatevConfig",
    "DatevError",
    "DatevAuthError",
    "DatevLicenseError",
    "program_keeps_revisions",
    "DatevConnectClient",
]
