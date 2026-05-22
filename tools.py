import io
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from log_config import logger

def sanitize_pdf(data: bytes) -> bytes:
    """
    Versucht, die PDF-Datei zu lesen und neu zu schreiben, falls nötig.
    Verändert nichts, wenn das Original ohne Fehler lesbar ist.
    Keine aktive Komprimierung.
    """
    try:
        # Versuch: Original ist bereits lesbar
        PdfReader(io.BytesIO(data))
        return data  # 👍 Kein Problem, unverändert zurückgeben

    except PdfReadError as read_error:
        logger.warning("sanitize_pdf: PDF unlesbar – versuche Reparatur: %s", read_error)

    except Exception as e:
        logger.warning("sanitize_pdf: Allgemeiner Fehler – versuche Reparatur: %s", e)

    # Reparaturversuch (nur wenn vorher Fehler auftrat)
    try:
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        repaired = buf.getvalue()
        logger.info("sanitize_pdf: PDF erfolgreich neu geschrieben.")
        return repaired
    except Exception as e:
        logger.warning("sanitize_pdf: Reparatur gescheitert – Original wird verwendet: %s", e)
        return data

from PIL import Image, ImageDraw

# Statischer Platzhalter (einmalig erzeugt)
PLACEHOLDER_PREVIEW = Image.new("RGB", (400, 300), (240, 240, 240))
draw = ImageDraw.Draw(PLACEHOLDER_PREVIEW)
draw.text((20, 140), "Vorschau wird berechnet...", fill="gray")
PLACEHOLDER_PREVIEW._is_placeholder = True
