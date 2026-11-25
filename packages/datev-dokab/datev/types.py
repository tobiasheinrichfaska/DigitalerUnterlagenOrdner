"""Core types for the DATEVconnect DMS v2 connector: config, an injected transport,
errors, and the program-type helper. HTTP is injected so the client is unit-testable
without a live DATEVconnect."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DatevConfig:
    base_url: str                       # e.g. https://localhost:58452/datev/api/dms/v2
    username: Optional[str] = None      # HTTP Basic UPN (user@domain); None ⇒ no Basic header
    password: Optional[str] = None
    allow_self_signed: bool = False     # tolerate DATEVconnect's self-signed localhost cert


@dataclass
class HttpResponse:
    status: int
    headers: dict = field(default_factory=dict)
    body: bytes = b""                   # raw bytes (binary-safe; text decoded by the caller)


# One HTTP exchange: (method, url, headers, body) -> HttpResponse. Injected; tests pass a fake.
Transport = Callable[[str, str, dict, Optional[bytes]], HttpResponse]


class DatevError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class DatevAuthError(DatevError):
    """A 401 from DATEVconnect (bad/missing credentials)."""


class DatevLicenseError(DatevError):
    """DATEVconnect reports a missing component license (e.g. Dokumentenmanagement,
    product 63218): auth worked but the feature is not licensed on this install."""


def program_keeps_revisions(feature: Optional[str]) -> bool:
    """Whether a file exchange is RETAINED as a revision for this program type
    (``GET /info`` → ``feature``). DokAB overwrites with no history; DokAbRev and DMS
    keep revisions. Decides whether 'update itself' is destructive on this install."""
    return (feature or "").strip().lower() in ("dokabrev", "dms")
