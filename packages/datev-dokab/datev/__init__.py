"""DATEVconnect Dokumentenablage (DMS v2) connector (package ``datev-dokab``).

A small, UI-free, injected-transport client + orchestration (``DatevService``) to read /
create / write back documents in the local DATEVconnect API. The package is headless, has no
UI and no dependencies beyond the standard library (Windows + ``curl.exe`` for the SSO
transport).

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
