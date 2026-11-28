# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""The PDF engine port — the impure boundary the data-driven commands call.

Engine-backed commands (compress/rotate/split/merge) need real byte work. They
talk to an ``Engine`` so their *structural* logic stays pure and testable with a
fake engine; ``RealEngine`` wraps the existing services / pypdf for production.
"""

from __future__ import annotations

import hashlib
import io
import logging
import sys
import threading
from collections import OrderedDict
from typing import List, Optional, Protocol, runtime_checkable

import pikepdf
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


_log = logging.getLogger(__name__)


def _cut_page_cross_references(pdf) -> None:
    """Prepare the (private, in-memory) parse of the source for copying single pages out of it.
    qpdf nulls references to other source pages on copy, which would leave DEAD internal links
    (GoTo/Dest -> null) in every part; drop those annotations. Also cut what would drag the
    siblings' structures along: an annotation's ``/P`` and (non-popup) ``/Parent`` (form-field
    trees reach the widgets of every other page) and article beads ``/B``."""
    for page_idx, page in enumerate(pdf.pages):
        obj = page.obj
        try:
            if "/B" in obj:
                del obj["/B"]
            annots = obj.get("/Annots")
            if annots is None:
                continue
            keep = pikepdf.Array()
            for a in annots:
                try:
                    if "/Dest" in a:
                        continue
                    act = a.get("/A")
                    if act is not None and act.get("/S") == pikepdf.Name.GoTo:
                        continue
                    if "/P" in a:
                        del a["/P"]
                    if "/Parent" in a and a.get("/Subtype") != pikepdf.Name.Popup:
                        del a["/Parent"]
                except Exception as exc:
                    _log.warning("annotation skipped on page %d: %r", page_idx, exc)
                    continue
                keep.append(a)
            obj["/Annots"] = keep
        except Exception as exc:
            _log.warning("annotation cleanup failed on page %d: %r", page_idx, exc)
            continue


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
        # in-flight compress_all_methods per key, so concurrent callers share one run (C-7)
        self._inflight: dict = {}
        # variants loaded from a .belegtool (persisted): NOT LRU-bounded, so every
        # node's saved variants stay available after reopening. Keyed like _mcache.
        # Guarded by _mcache_lock too — seed_variants writes it during open() while
        # variants_for/evaluated iterate it on other pywebview threads.
        self._persisted: dict = {}
        # PF-2: digest -> {dpi: True} index over _persisted (ordered), so variants_for /
        # evaluated are O(1) per leaf instead of scanning every persisted entry.
        # Guarded by _mcache_lock like _persisted itself.
        self._pidx: dict = {}
        # identity-memoised sha1 (the model's bytes are immutable, so a given bytes
        # object hashes once) — _doc_response_locked calls variants_for/evaluated per
        # leaf on EVERY edit while holding the CoreApi lock; without the memo each
        # call re-hashes the document's full bytes. Same pattern as CoreApi._version_of.
        # The strong ref to the bytes is what makes id-keying safe; evicting only by
        # entry count could pin 256 FULL leaf byte-strings (incl. closed sessions'),
        # so eviction is ALSO byte-budgeted. An evicted entry simply re-hashes.
        self._dcache: "OrderedDict[int, tuple]" = OrderedDict()
        self._dcache_lock = threading.Lock()
        self._dcache_bytes = 0
        self._dcache_max_entries = 256
        self._dcache_budget = 64 * 1024 * 1024
        # PF-1: identity memo WITHOUT a count/byte cap. The documents' own leaf bytes
        # are alive anyway, so the memo adds no copies; what it must not do is pin
        # bytes nobody else holds (closed sessions). Entries whose only remaining
        # referrers are the memo itself are swept, amortised (see _sweep_dlive). The
        # small budgeted LRU above stays as the second layer (unchanged semantics).
        self._dlive: dict = {}
        self._dlive_sweep_at = 512
        # R10-4: pinned BYTES are bounded too — a sweep also runs once the memo pins more
        # than max(64 MiB, 2x the bytes that were still live after the last sweep).
        self._dlive_bytes = 0
        self._dlive_sweep_bytes = 64 * 1024 * 1024

    def _sweep_dlive(self) -> None:
        """Drop identity-memo entries whose bytes nothing else references any more.
        Caller holds _dcache_lock. Baseline refs of an otherwise-unreferenced entry:
        the _dlive tuple, (the _dcache tuple if present) and getrefcount's argument."""
        for key, ent in list(self._dlive.items()):
            b = ent[0]
            base = 2 + (1 if (key in self._dcache and self._dcache[key][0] is b) else 0)
            if sys.getrefcount(b) <= base + 1:  # +1: the local ``b``
                del self._dlive[key]
        self._dlive_sweep_at = max(512, 2 * len(self._dlive))
        self._dlive_bytes = sum(len(e[0]) for e in self._dlive.values())
        self._dlive_sweep_bytes = max(64 * 1024 * 1024, 2 * self._dlive_bytes)

    def _digest(self, pdf_bytes: bytes) -> bytes:
        key = id(pdf_bytes)
        with self._dcache_lock:
            ent = self._dlive.get(key)
            if ent is not None and ent[0] is pdf_bytes:
                return ent[1]
            ent = self._dcache.get(key)
            if ent is not None and ent[0] is pdf_bytes:
                self._dcache.move_to_end(key)
                return ent[1]
        d = hashlib.sha1(pdf_bytes).digest()
        with self._dcache_lock:
            if (len(self._dlive) >= self._dlive_sweep_at
                    or self._dlive_bytes + len(pdf_bytes) > self._dlive_sweep_bytes):
                self._sweep_dlive()
            if key not in self._dlive:
                self._dlive_bytes += len(pdf_bytes)
            self._dlive[key] = (pdf_bytes, d)
        if len(pdf_bytes) > self._dcache_budget:
            # a single object larger than the whole budget can't stay in the LRU layer —
            # caching it would just drain every other entry, then evict itself.
            return d
        with self._dcache_lock:
            # the cache holds the bytes, so a live id can't be reused for other bytes
            old = self._dcache.pop(key, None)
            if old is not None:  # defensive — a live entry's id can't actually collide
                self._dcache_bytes -= len(old[0])
            self._dcache[key] = (pdf_bytes, d)
            self._dcache_bytes += len(pdf_bytes)
            while self._dcache and (len(self._dcache) > self._dcache_max_entries
                                    or self._dcache_bytes > self._dcache_budget):
                _k, (old_bytes, _d) = self._dcache.popitem(last=False)
                self._dcache_bytes -= len(old_bytes)
        return d

    def variants_for(self, pdf_bytes: bytes) -> dict:
        """All known variants for this source as ``{dpi: {method: bytes}}`` — both
        freshly computed (hot cache) and loaded from file — for persistence on save."""
        digest = self._digest(pdf_bytes)
        out: dict = {}
        with self._mcache_lock:
            # _mcache is capped at _mcache_max (16) entries: a scan is O(1). The
            # persisted layer is unbounded → looked up through the digest index (PF-2).
            for (d, dpi), result in self._mcache.items():
                if d == digest and result:
                    out.setdefault(dpi, {}).update(result)
            for dpi in self._pidx.get(digest, ()):
                result = self._persisted.get((digest, dpi))
                if result:
                    out.setdefault(dpi, {}).update(result)
        return out

    def evaluated(self, pdf_bytes: bytes) -> bool:
        """True if this source has been run through compress_all_methods at least once
        (any DPI) — hot or persisted. Distinguishes 'not yet checked' from 'checked,
        nothing smaller found' (both yield empty variants_for), which the UI needs for
        the 'compression undecided' marker."""
        digest = self._digest(pdf_bytes)
        with self._mcache_lock:
            return (any(d == digest for (d, _dpi) in self._mcache)
                    or bool(self._pidx.get(digest)))

    def seed_variants(self, pdf_bytes: bytes, variants: dict) -> None:
        """Load persisted variants (``{dpi: {method: bytes}}``) so re-selecting the
        node is instant — no recompute. The layer is unbounded while its documents
        are open; ``prune_persisted`` frees it when they close."""
        digest = self._digest(pdf_bytes)
        try:
            src_pages = self.page_count(pdf_bytes)
        except Exception:
            src_pages = None  # unreadable source: nothing to compare against

        def _ok(vb) -> bool:
            # same guard as fresh candidates (SV-4): a variant whose page count
            # differs from the source would shift every following node on reload
            if src_pages is None:
                return True
            try:
                return self.page_count(vb) == src_pages
            except Exception:
                return True  # unparseable: not a count mismatch (opaque/test blobs); Compress surfaces it

        for dpi, methods in (variants or {}).items():
            kept = {m: vb for m, vb in (methods or {}).items() if _ok(vb)}
            if kept:
                with self._mcache_lock:
                    self._persisted[(digest, int(dpi))] = kept
                    self._pidx.setdefault(digest, {})[int(dpi)] = True

    def prune_persisted(self, closed_sources, live_sources) -> None:
        """Drop the persisted variants of the CLOSED document's sources, keeping
        any that another open document still shares. Without this, every opened
        .belegtool's variant bytes stayed pinned for the whole app run (audit
        2026-11-03, L6). Scoped to closed−live (not "everything not live"): open()
        seeds variants BEFORE registering the session, so a concurrent close must
        not sweep those fresh seeds away. Hashing is id-memoised → cheap."""
        drop = {self._digest(b) for b in closed_sources if b}
        drop -= {self._digest(b) for b in live_sources if b}
        if not drop:
            return
        with self._mcache_lock:
            for dg in drop:
                for dpi in self._pidx.pop(dg, ()):
                    self._persisted.pop((dg, dpi), None)

    def _all_methods(self, pdf_bytes: bytes, dpi: int, cancel=None) -> dict:
        key = (self._digest(pdf_bytes), dpi)
        with self._mcache_lock:
            persisted = self._persisted.get(key)
        if persisted is not None:
            return persisted
        with self._mcache_lock:
            hit = self._mcache.get(key)
            if hit is not None:
                self._mcache.move_to_end(key)
                return hit
        with self._mcache_lock:
            waiter = self._inflight.get(key)
            if waiter is None:
                self._inflight[key] = threading.Event()
        if waiter is not None:
            waiter.wait()  # another thread computes the same key — reuse its result
            with self._mcache_lock:
                hit = self._mcache.get(key) or self._persisted.get(key)
            if hit is not None:
                return hit
            return self._all_methods(pdf_bytes, dpi, cancel)  # it was cancelled/failed: retry
        try:
            from formats.compress_pdf_bytes import compress_all_methods, CompressionCancelled
            try:
                result = compress_all_methods(pdf_bytes, dpi=dpi, cancel=cancel)  # smaller-than-original
            except CompressionCancelled:
                return {}  # node was removed mid-compress → don't memoise a partial/empty result
            with self._mcache_lock:
                self._mcache[key] = result
                if len(self._mcache) > self._mcache_max:
                    self._mcache.popitem(last=False)  # evict the least-recently-used
            return result
        finally:
            with self._mcache_lock:
                ev = self._inflight.pop(key, None)
            if ev is not None:
                ev.set()

    def page_count(self, pdf_bytes: bytes) -> int:
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)

    def compress(self, pdf_bytes: bytes, dpi: int, method=None, cancel=None) -> Optional[bytes]:
        results = self._all_methods(pdf_bytes, dpi, cancel)
        if not results:
            return None
        if method is not None:
            return results.get(method)  # None if that method wasn't smaller
        return min(results.values(), key=len)  # best (smallest)

    def compress_methods(self, pdf_bytes: bytes, dpi: int, cancel=None) -> dict:
        return {m: len(b) for m, b in self._all_methods(pdf_bytes, dpi, cancel).items()}

    def rotate(self, pdf_bytes: bytes, angle: int) -> bytes:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        # clone the whole document (not page-by-page) so the catalog survives — notably
        # /AcroForm; add_page alone dropped it and left orphaned widgets (C-6)
        writer = PdfWriter(clone_from=reader)
        # the old page-by-page path dropped the catalog; keep /AcroForm but never carry
        # document-level active content (OpenAction / additional actions / JS name tree)
        root = writer._root_object
        for key in ("/OpenAction", "/AA"):
            if key in root:
                del root[key]
        names = root.get("/Names")
        if names is not None:
            names = names.get_object()
            if "/JavaScript" in names:
                del names["/JavaScript"]
        for page in writer.pages:
            page.rotate(angle)
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
        # Direct page-range copy via pikepdf: one source parse instead of N (the old
        # per-page split + merge re-parsed per page). Inherited page-tree attributes
        # (MediaBox/Rotate/CropBox/Resources) are materialised by qpdf's page copy.
        # Deliberate limit (like the export path): internal link/GoTo annotations are
        # dropped (their targets live in other chunks); URI links stay. Outlines and the
        # AcroForm tree are not carried.
        size = max(1, int(size))
        out: List[tuple] = []
        with pikepdf.open(io.BytesIO(pdf_bytes), suppress_warnings=True) as src:
            _cut_page_cross_references(src)
            n = len(src.pages)
            for i in range(0, n, size):
                last = min(i + size, n)
                with pikepdf.Pdf.new() as dst:
                    dst.pages.extend(src.pages[i:last])
                    buf = io.BytesIO()
                    dst.save(buf)
                out.append((buf.getvalue(), last - i))
        return out

    def merge(self, parts: List[bytes]) -> bytes:
        writer = PdfWriter()
        for part in parts:
            for page in PdfReader(io.BytesIO(part)).pages:
                writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
