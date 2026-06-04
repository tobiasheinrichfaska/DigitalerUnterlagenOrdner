"""Serialize a node's computed compression variants to/from a single blob, for
embedding in the .belegtool as a per-node attachment.

Layout: a ZIP (stored, no extra compression — the variants are already compressed
PDFs) whose entries are ``"<dpi>/<method>"`` → the variant's PDF bytes. ZIP is used
(not pickle) so loading an untrusted file can never execute code.
"""

from __future__ import annotations

import io
import zipfile


def pack(variants: dict) -> bytes:
    """``{dpi: {method: bytes}}`` → blob bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for dpi, methods in variants.items():
            for method, data in (methods or {}).items():
                if data:
                    z.writestr(f"{int(dpi)}/{method}", data)
    return buf.getvalue()


def unpack(blob: bytes) -> dict:
    """blob bytes → ``{dpi: {method: bytes}}`` (best-effort; bad entries skipped)."""
    out: dict = {}
    try:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as z:
            for name in z.namelist():
                dpi_s, sep, method = name.partition("/")
                if not sep or not method:
                    continue
                try:
                    dpi = int(dpi_s)
                except ValueError:
                    continue
                out.setdefault(dpi, {})[method] = z.read(name)
    except (zipfile.BadZipFile, OSError):
        return {}
    return out
