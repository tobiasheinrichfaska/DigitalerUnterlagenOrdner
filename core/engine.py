"""The PDF engine port — the impure boundary the data-driven commands call.

Engine-backed commands (compress/rotate/split/merge) need real byte work. They
talk to an ``Engine`` so their *structural* logic stays pure and testable with a
fake engine; ``RealEngine`` wraps the existing services / pypdf for production.
"""

from __future__ import annotations

import hashlib
import io
import threading
from collections import OrderedDict
from typing import List, Optional, Protocol, runtime_checkable

from pypdf import PdfReader, PdfWriter


@runtime_checkable
class Engine(Protocol):
    def page_count(self, pdf_bytes: bytes) -> int: ...

    def compress(self, pdf_bytes: bytes, dpi: int, method=None) -> Optional[bytes]:
        """Smaller re-encoded PDF. ``method`` picks one (jpg/png/pikepdf); None = best.
        Returns None if that method didn't beat the original."""

    def compress_methods(self, pdf_bytes: bytes, dpi: int) -> dict:
        """Map of method -> result size, only for methods smaller than the original."""

    def rotate(self, pdf_bytes: bytes, angle: int) -> bytes:
        """All pages rotated by ``angle`` degrees (multiple of 90)."""

    def split(self, pdf_bytes: bytes) -> List[bytes]:
        """One single-page PDF per page (used in D3b)."""

    def split_chunks(self, pdf_bytes: bytes, size: int) -> List[tuple]:
        """``(pdf_bytes, page_count)`` for consecutive chunks of ``size`` pages —
        direct page-range copy (avoids the per-page split + re-merge round-trip)."""

    def merge(self, parts: List[bytes]) -> bytes:
        """Concatenate PDFs page-by-page (used in D3b)."""


class RealEngine:
    """Production engine: pypdf for structure, compress_pdf_bytes for compression.

    Memoises ``compress_all_methods`` per (content, dpi) so re-selecting a node
    doesn't recompute its compressions. Keyed by a hash of the bytes, so it stays
    valid as long as the node's bytes are unchanged and invalidates automatically
    when they change (rotate/compress/import). Bounded LRU to cap memory.
    """

    def __init__(self):
        self._mcache: "OrderedDict[tuple, dict]" = OrderedDict()
        self._mcache_max = 16
        self._mcache_lock = threading.Lock()

    def _all_methods(self, pdf_bytes: bytes, dpi: int) -> dict:
        key = (hashlib.sha1(pdf_bytes).digest(), dpi)
        with self._mcache_lock:
            hit = self._mcache.get(key)
            if hit is not None:
                self._mcache.move_to_end(key)
                return hit
        from compress_pdf_bytes import compress_all_methods
        result = compress_all_methods(pdf_bytes, dpi=dpi)  # only smaller-than-original
        with self._mcache_lock:
            self._mcache[key] = result
            if len(self._mcache) > self._mcache_max:
                self._mcache.popitem(last=False)  # evict the least-recently-used
        return result

    def page_count(self, pdf_bytes: bytes) -> int:
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

    def compress(self, pdf_bytes: bytes, dpi: int, method=None) -> Optional[bytes]:
        results = self._all_methods(pdf_bytes, dpi)
        if not results:
            return None
        if method is not None:
            return results.get(method)  # None if that method wasn't smaller
        return min(results.values(), key=len)  # best (smallest)

    def compress_methods(self, pdf_bytes: bytes, dpi: int) -> dict:
        return {m: len(b) for m, b in self._all_methods(pdf_bytes, dpi).items()}

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

    def split_chunks(self, pdf_bytes: bytes, size: int) -> List[tuple]:
        # Direct page-range copy via PyMuPDF — ~7x faster than per-page split + merge
        # for chunked splits, and one source parse instead of N.
        import fitz
        size = max(1, int(size))
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            n = src.page_count
            out: List[tuple] = []
            for i in range(0, n, size):
                last = min(i + size - 1, n - 1)
                d = fitz.open()
                try:
                    d.insert_pdf(src, from_page=i, to_page=last)
                    out.append((d.tobytes(), last - i + 1))
                finally:
                    d.close()
            return out
        finally:
            src.close()

    def merge(self, parts: List[bytes]) -> bytes:
        writer = PdfWriter()
        for part in parts:
            for page in PdfReader(io.BytesIO(part)).pages:
                writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
