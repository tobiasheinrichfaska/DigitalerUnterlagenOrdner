import io
import pikepdf
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from infra.log_config import logger

# Deflate-bomb guard for the repair step: pikepdf re-encodes (and may inflate)
# streams without a decoded-size bound. A genuine repaired PDF stays within a small
# multiple of its input; a bomb explodes far past it. Cap at max(absolute, ratio×in)
# and discard the repair when it blows the cap (the original — unreadable — is
# returned, so downstream fitz/pypdf just fails normally instead of OOMing here).
_REPAIR_ABS_CAP = 500 * 1024 * 1024  # 500 MB, mirrors the archive caps
_REPAIR_RATIO = 50


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
    cap = max(_REPAIR_ABS_CAP, len(data) * _REPAIR_RATIO)
    try:
        with pikepdf.open(io.BytesIO(data), suppress_warnings=True) as pdf:
            buf = io.BytesIO()
            pdf.save(buf, compress_streams=True)
            repaired = buf.getvalue()
        if len(repaired) > cap:
            logger.warning(
                "sanitize_pdf: Reparatur produzierte %d Bytes (> %d, mögliche Deflate-Bombe) "
                "– Reparatur verworfen.", len(repaired), cap)
            return data
        logger.info("sanitize_pdf: PDF erfolgreich via pikepdf repariert.")
        return repaired
    except Exception as e:
        logger.warning("sanitize_pdf: Reparatur gescheitert – Original wird verwendet: %s", e)
        return data
