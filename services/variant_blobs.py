"""Serialize a node's computed compression variants to/from a single blob, for
embedding in the .belegtool as a per-node attachment.

Layout: a ZIP (stored, no extra compression — the variants are already compressed
PDFs) whose entries are ``"<dpi>/<method>"`` → the variant's PDF bytes. ZIP is used
(not pickle) so loading an untrusted file can never execute code.
"""

from __future__ import annotations

import io
import zipfile

# Bomb guards (mirroring universal_importer/archives.py): the blob comes from an
# untrusted .belegtool and is decompressed automatically on open() — a deflate
# bomb must never balloon. Declared sizes lie, so the ACTUAL read is capped.
MAX_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MB unpacked per blob
MAX_ENTRIES = 500


def pack(variants: dict) -> bytes:
    """``{dpi: {method: bytes}}`` → blob bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for dpi, methods in variants.items():
            for method, data in (methods or {}).items():
                if data:
                    z.writestr(f"{int(dpi)}/{method}", data)
    return buf.getvalue()


def unpack(blob: bytes, max_total_bytes: int = MAX_TOTAL_BYTES,
           max_entries: int = MAX_ENTRIES) -> dict:
    """blob bytes → ``{dpi: {method: bytes}}`` (best-effort; bad entries skipped).
    A blob that exceeds the entry-count or unpacked-size caps is discarded whole
    (``{}``) — the variants then simply recompute; never trade safety for them."""
    out: dict = {}
    try:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as z:
            names = z.namelist()
            if len(names) > max_entries:
                return {}
            total = 0
            for name in names:
                dpi_s, sep, method = name.partition("/")
                if not sep or not method:
                    continue
                try:
                    dpi = int(dpi_s)
                except ValueError:
                    continue
                # actual-read cap: read at most the remaining budget + 1 byte —
                # an entry whose real size exceeds it reveals itself without
                # ever allocating the full bomb.
                remaining = max_total_bytes - total
                with z.open(name) as f:
                    data = f.read(remaining + 1)
                if len(data) > remaining:
                    return {}
                total += len(data)
                out.setdefault(dpi, {})[method] = data
    except (zipfile.BadZipFile, OSError):
        return {}
    return out
