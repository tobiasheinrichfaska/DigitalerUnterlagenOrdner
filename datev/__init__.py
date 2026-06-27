"""DATEVconnect Dokumentenablage (DMS v2) connector for BelegTool.

A small, UI-free, injected-transport client + probe logic so we can read (and later
create / exchange) documents in the local DATEVconnect API, governed by a Tkinter GUI.
See ``docs/datev-probe.md`` for the plan and the read/create/exchange rounds.

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
