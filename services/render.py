"""Headless PDF preview rendering — no Tk, no GUI.

Pure functions: PDF bytes -> page images / PNG bytes. Extracted from
``PDFNode._create_previews`` so the domain model no longer renders previews
itself (Phase 1 of the React migration).

- ``render_pdf_to_images`` returns PIL images — what the current Tkinter app
  needs (it wraps them in ImageTk for the canvas).
- ``render_pdf_to_pngs`` returns PNG bytes — the web/React-facing form
  (the SPA shows them via ``<img>``); also the shape the core service will
  send over IPC.
"""

import io
from typing import List, Optional, Union

import fitz
from PIL import Image

from infra.log_config import logger

DEFAULT_PREVIEW_DPI = 100


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
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception as e:
            logger.warning("PDF konnte nicht geöffnet werden (fitz): %s", e)
            return []

        previews: List[Image.Image] = []
        try:
            for page in doc:
                try:
                    pix = page.get_pixmap(dpi=dpi)
                    ppm_bytes = pix.tobytes("ppm")
                    if not ppm_bytes.startswith(b"P6"):
                        logger.warning(
                            "Ungültiger PPM-Header auf Seite %d – Vorschau abgebrochen.",
                            page.number)
                        continue
                    with Image.open(io.BytesIO(ppm_bytes)) as im:
                        img = im.convert("RGB").copy()
                    previews.append(img)
                except Exception as e:
                    logger.warning("Vorschaufehler auf Seite %d: %s", page.number, e)
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
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        logger.warning("render_page: PDF konnte nicht geöffnet werden: %s", e)
        return b""
    try:
        if page_index < 0 or page_index >= doc.page_count:
            return b""
        pix = doc[page_index].get_pixmap(dpi=dpi)
        ppm = pix.tobytes("ppm")
        if not ppm.startswith(b"P6"):
            return b""
        with Image.open(io.BytesIO(ppm)) as im:
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning("render_page: Fehler auf Seite %d: %s", page_index, e)
        return b""
    finally:
        doc.close()


def page_count(data: Optional[Union[bytes, io.BytesIO]]) -> int:
    """Cheap page count (no rasterizing)."""
    raw = _raw(data)
    if not raw:
        return 0
    try:
        with fitz.open(stream=raw, filetype="pdf") as doc:
            return doc.page_count
    except Exception:
        return 0


def page_dims(data: Optional[Union[bytes, io.BytesIO]]) -> List[tuple]:
    """``(width, height)`` in points for every page — for stable placeholder
    boxes in the virtualized scroller (no rasterizing)."""
    raw = _raw(data)
    if not raw:
        return []
    try:
        with fitz.open(stream=raw, filetype="pdf") as doc:
            return [(p.rect.width, p.rect.height) for p in doc]
    except Exception:
        return []
