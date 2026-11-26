# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Headless PDF preview rendering — no Tk, no GUI.

Pure functions: PDF bytes -> page images / PNG bytes. Extracted from
``PDFNode._create_previews`` so the domain model no longer renders previews
itself (Phase 1 of the React migration).

Rasterizing goes through ``belegtool_compress.raster`` (pypdfium2 behind a process-wide priority lock; an
interactive page overtakes background prefetch/compression work, see ``docs/pdfium-spike.md``).

- ``render_pdf_to_images`` returns PIL images — the headless/test-facing form
  (used by tests and the compression raster path; no GUI canvas anymore).
- ``render_pdf_to_pngs`` returns PNG bytes — the web/React-facing form
  (the SPA shows them via ``<img>``); also the shape the core service will
  send over IPC.
"""

import io
from typing import List, Optional, Union

from PIL import Image

from belegtool_compress import pdfinfo as _pdfinfo
from belegtool_compress import raster

from infra.log_config import logger

DEFAULT_PREVIEW_DPI = 100

# Pixel budget per rendered page: a hostile/oversized MediaBox (up to 200×200 in)
# would otherwise make the rasterizer allocate GBs. ~64 MP ≈ 192 MB RGB — far above
# any legitimate page at preview DPI, so normal renders are never affected.
MAX_RENDER_PIXELS = 64_000_000


def _cap_dpi(width_pt: float, height_pt: float, dpi: int) -> int:
    """Clamp ``dpi`` down so a width x height (pt) page renders within MAX_RENDER_PIXELS."""
    px = (width_pt * dpi / 72.0) * (height_pt * dpi / 72.0)
    if px <= MAX_RENDER_PIXELS or px <= 0:
        return dpi
    import math
    capped = max(1, int(dpi * math.sqrt(MAX_RENDER_PIXELS / px)))
    logger.warning("Übergroße Seite (%.0f×%.0f pt) – DPI von %d auf %d begrenzt.",
                   width_pt, height_pt, dpi, capped)
    return capped


def capped_dpi(page, dpi: int) -> int:
    """Clamp ``dpi`` down so the page (an object with ``.rect.width/.height``) renders within
    MAX_RENDER_PIXELS."""
    return _cap_dpi(page.rect.width, page.rect.height, dpi)


_capped_dpi = capped_dpi  # back-compat alias for existing callers/tests


def _render_index(doc, index: int, dpi: int) -> Image.Image:
    w, h = doc.page_size(index)
    return doc.render(index, _cap_dpi(w, h, dpi))


def render_pdf_to_images(
    data: Optional[Union[bytes, io.BytesIO]],
    dpi: int = DEFAULT_PREVIEW_DPI,
) -> List[Image.Image]:
    """Render every page of a PDF to an RGB PIL image.

    Returns an empty list on empty/invalid input or if no page could be
    rendered (callers treat ``[]`` as "no valid preview").
    """
    if not data:
        logger.warning("Leere PDF-Daten – Vorschau abgebrochen.")
        return []

    try:
        raw = data.getvalue() if isinstance(data, io.BytesIO) else data
        if not raw:
            return []

        try:
            doc = raster.open_pdf(raw)
        except Exception as e:
            logger.warning("PDF konnte nicht geöffnet werden (Rasterizer): %s", e)
            return []

        previews: List[Image.Image] = []
        try:
            for index in range(doc.page_count):
                try:
                    previews.append(_render_index(doc, index, dpi))
                except Exception as e:
                    logger.warning("Vorschaufehler auf Seite %d: %s", index, e)
                    continue
        finally:
            doc.close()

        if not previews:
            logger.warning("Keine Seitenvorschau möglich – alle Seiten fehlerhaft?")
        return previews

    except Exception as e:
        logger.error("FEHLER bei Vorschau-Erzeugung: %s", e)
        return []


def render_pdf_to_pngs(
    data: Optional[Union[bytes, io.BytesIO]],
    dpi: int = DEFAULT_PREVIEW_DPI,
) -> List[bytes]:
    """Render every page to PNG bytes (web/React-facing form)."""
    pngs: List[bytes] = []
    for img in render_pdf_to_images(data, dpi=dpi):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pngs.append(buf.getvalue())
    return pngs


def _raw(data: Optional[Union[bytes, io.BytesIO]]) -> bytes:
    if not data:
        return b""
    return data.getvalue() if isinstance(data, io.BytesIO) else data


def render_page(
    data: Optional[Union[bytes, io.BytesIO]],
    page_index: int,
    dpi: int = DEFAULT_PREVIEW_DPI,
) -> bytes:
    """Render a **single** page to PNG bytes (the windowed-cache unit).

    Returns ``b""`` on empty/invalid input or an out-of-range page, so callers
    can treat empty as "no preview" without raising.
    """
    raw = _raw(data)
    if not raw:
        return b""
    try:
        doc = raster.open_pdf(raw)
    except Exception as e:
        logger.warning("render_page: PDF konnte nicht geöffnet werden: %s", e)
        return b""
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return b""
        img = _render_index(doc, page_index, dpi)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning("render_page: Fehler auf Seite %d: %s", page_index, e)
        return b""
    finally:
        doc.close()


def page_count(data: Optional[Union[bytes, io.BytesIO]]) -> int:
    """Cheap page count (no rasterizing; pikepdf, see ``belegtool_compress.pdfinfo``)."""
    return _pdfinfo.page_count(data)


def page_dims(data: Optional[Union[bytes, io.BytesIO]]) -> List[tuple]:
    """``(width, height)`` in points for every page — for stable placeholder
    boxes in the virtualized scroller (no rasterizing; pikepdf, rotation/CropBox/
    UserUnit-aware, see ``belegtool_compress.pdfinfo``)."""
    return _pdfinfo.page_dims(data)
