import io
import pikepdf
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from log_config import logger

def sanitize_pdf(data: bytes) -> bytes:
    """
    Versucht, die PDF-Datei zu lesen und neu zu schreiben, falls nötig.
    Verändert nichts, wenn das Original ohne Fehler lesbar ist.
    Keine aktive Komprimierung.

    Der Reparaturversuch nutzt pikepdf, das viele praxisübliche Korruptionen
    beheben kann (fehlende xref-Tabellen, kaputte Objekt-Streams usw.).
    """
    try:
        # Versuch: Original ist bereits lesbar
        PdfReader(io.BytesIO(data))
        return data  # Kein Problem, unverändert zurückgeben

    except PdfReadError as read_error:
        logger.warning("sanitize_pdf: PDF unlesbar – versuche Reparatur: %s", read_error)

    except Exception as e:
        logger.warning("sanitize_pdf: Allgemeiner Fehler – versuche Reparatur: %s", e)

    # Reparaturversuch via pikepdf (behandelt kaputte xref-Tabellen / Objekt-Streams)
    try:
        with pikepdf.open(io.BytesIO(data), suppress_warnings=True) as pdf:
            buf = io.BytesIO()
            pdf.save(buf, compress_streams=True)
            repaired = buf.getvalue()
        logger.info("sanitize_pdf: PDF erfolgreich via pikepdf repariert.")
        return repaired
    except Exception as e:
        logger.warning("sanitize_pdf: Reparatur gescheitert – Original wird verwendet: %s", e)
        return data
