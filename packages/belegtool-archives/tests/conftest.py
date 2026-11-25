"""Test setup: the library needs a host-injected converter for non-PDF members. The legacy tests were
written against the host's real converter (images/HTML -> PDF); here a deterministic fake stands in for it
by replacing the library's fallback converter. `ORIGINAL_DEFAULT` keeps the real fallback for its own tests."""

import io
import os

import pytest

from belegtool_archives import archives
from helpers import create_valid_pdf

ORIGINAL_DEFAULT = archives._default_convert_member


def fake_host_convert(content: bytes, name: str) -> io.BytesIO:
    """Stand-in for the host converter: PDFs pass through, other known formats become a 1-page PDF,
    a disguised executable is refused (like the host's signature gate)."""
    if content[:2] == b"MZ":
        raise ValueError("Windows-Programm als Dokument getarnt")
    ext = os.path.splitext(name or "")[1].lower()
    if ext == ".pdf":
        return io.BytesIO(content)
    return io.BytesIO(create_valid_pdf(1))


@pytest.fixture(autouse=True)
def _host_converter(monkeypatch, request):
    if request.module.__name__ == "test_convert_injection":
        return
    monkeypatch.setattr(archives, "_default_convert_member", fake_host_convert)
