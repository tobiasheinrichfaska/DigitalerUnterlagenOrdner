"""The PDF engine port — the impure boundary the data-driven commands call.

Engine-backed commands (compress/rotate/split/merge) need real byte work. They
talk to an ``Engine`` so their *structural* logic stays pure and testable with a
fake engine; ``RealEngine`` wraps the existing services / pypdf for production.
"""

from __future__ import annotations

import io
from typing import List, Optional, Protocol, runtime_checkable

from pypdf import PdfReader, PdfWriter


@runtime_checkable
class Engine(Protocol):
    def page_count(self, pdf_bytes: bytes) -> int: ...

    def compress(self, pdf_bytes: bytes, dpi: int) -> Optional[bytes]:
        """Smaller re-encoded PDF, or None if no method beat the original."""

    def rotate(self, pdf_bytes: bytes, angle: int) -> bytes:
        """All pages rotated by ``angle`` degrees (multiple of 90)."""

    def split(self, pdf_bytes: bytes) -> List[bytes]:
        """One single-page PDF per page (used in D3b)."""

    def merge(self, parts: List[bytes]) -> bytes:
        """Concatenate PDFs page-by-page (used in D3b)."""


class RealEngine:
    """Production engine: pypdf for structure, compress_pdf_bytes for compression."""

    def page_count(self, pdf_bytes: bytes) -> int:
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

    def compress(self, pdf_bytes: bytes, dpi: int) -> Optional[bytes]:
        from compress_pdf_bytes import compress_all_methods
        results = compress_all_methods(pdf_bytes, dpi=dpi)
        if not results:
            return None
        best = min(results.values(), key=len)
        return best if len(best) < len(pdf_bytes) else None

    def rotate(self, pdf_bytes: bytes, angle: int) -> bytes:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            page.rotate(angle)
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()

    def split(self, pdf_bytes: bytes) -> List[bytes]:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: List[bytes] = []
        for page in reader.pages:
            writer = PdfWriter()
            writer.add_page(page)
            buf = io.BytesIO()
            writer.write(buf)
            parts.append(buf.getvalue())
        return parts

    def merge(self, parts: List[bytes]) -> bytes:
        writer = PdfWriter()
        for part in parts:
            for page in PdfReader(io.BytesIO(part)).pages:
                writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
