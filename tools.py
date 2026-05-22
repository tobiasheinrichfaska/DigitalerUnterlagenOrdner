import io
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

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
        print(f"[sanitize_pdf] PDF unlesbar – versuche Reparatur: {read_error}")

    except Exception as e:
        print(f"[sanitize_pdf] Allgemeiner Fehler – versuche Reparatur: {e}")

    # Reparaturversuch (nur wenn vorher Fehler auftrat)
    try:
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        repaired = buf.getvalue()
        print(f"[sanitize_pdf] PDF erfolgreich neu geschrieben nach Fehler")
        return repaired
    except Exception as e:
        print(f"[sanitize_pdf] Reparatur gescheitert – Original wird verwendet: {e}")
        return data

from PIL import Image, ImageDraw

# Statischer Platzhalter (einmalig erzeugt)
PLACEHOLDER_PREVIEW = Image.new("RGB", (400, 300), (240, 240, 240))
draw = ImageDraw.Draw(PLACEHOLDER_PREVIEW)
draw.text((20, 140), "Vorschau wird berechnet...", fill="gray")
PLACEHOLDER_PREVIEW._is_placeholder = True
