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

from log_config import logger

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
