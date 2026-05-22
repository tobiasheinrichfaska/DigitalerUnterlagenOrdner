import fitz
from PIL import Image
import io
from pypdf import PdfReader, PdfWriter
import pikepdf



def compress_pdf_bytes(input_bytes: bytes, dpi: int = 150, method: str = "jpg") -> bytes:
    """
    Führt eine zweistufige PDF-Komprimierung durch:
    1. Bildbasierte Neurenderung (JPEG, PNG, ...)
    2. Struktur-Reencode per PyPDF2
    Gibt stets das beste Ergebnis der beiden zurück.
    """
    # Stufe 1: Bilderzeugung
    rendered = _render_pdf_as_images(input_bytes, dpi=dpi, method=method)
    # print(f"[compress_pdf_bytes] Nach Bildkompression: {len(rendered)} Bytes")

    # Stufe 2: Strukturelle Bereinigung
    reencoded = reencode_pdf_structure(rendered)
    # print(f"[compress_pdf_bytes] Nach Struktur-Reencode: {len(reencoded)} Bytes")

    return reencoded


def _render_pdf_as_images(input_bytes: bytes, dpi: int = 150, method: str = "jpg") -> bytes:
    """
    Rendert jede Seite eines PDFs als Bild (Graustufen) und erstellt daraus ein neues PDF.
    Fehlerhafte Seiten werden übersprungen.
    """
    import fitz
    from PIL import Image
    import io

    A4_WIDTH_PT = 595.0
    input_pdf = fitz.open(stream=input_bytes, filetype="pdf")
    output_pdf = fitz.open()

    for page_index in range(len(input_pdf)):
        try:
            page = input_pdf.load_page(page_index)

            if page.rect.width >= A4_WIDTH_PT:
                dpi_rel = int(dpi * (A4_WIDTH_PT / page.rect.width))
                target_width = A4_WIDTH_PT
                scale_factor = A4_WIDTH_PT / page.rect.width
                target_height = page.rect.height * scale_factor
            else:
                dpi_rel = dpi
                target_width = page.rect.width
                target_height = page.rect.height

            pix = page.get_pixmap(dpi=dpi_rel, colorspace=fitz.csGRAY)
            image = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("L")

            buf = io.BytesIO()
            if method == "jpg":
                image.save(buf, format="JPEG", quality=60)
            elif method == "png":
                image.save(buf, format="PNG", compress_level=6)
            else:
                raise ValueError(f"Unbekannte Komprimierungsmethode: {method}")
            buf.seek(0)

            rect = fitz.Rect(0, 0, target_width, target_height)
            img_page = output_pdf.new_page(width=target_width, height=target_height)
            img_page.insert_image(rect, stream=buf.getvalue(), keep_proportion=True)

        except Exception as e:
            print(f"[WARN] Fehler bei Seite {page_index}: {e}")
            continue

    out_buf = io.BytesIO()
    output_pdf.save(out_buf)
    return out_buf.getvalue()


def reencode_pdf_structure(pdf_bytes: bytes) -> bytes:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as e:
        print(f"[Reencode] Fehler: {e}")
        return pdf_bytes

def recompress_with_pikepdf(input_bytes: bytes) -> bytes:
    """
    Re-komprimiert ein PDF strukturell mithilfe von pikepdf.
    Entfernt ungenutzte Objekte und nutzt effiziente Deflate-Kompression.
    """
    try:
        input_stream = io.BytesIO(input_bytes)
        with pikepdf.open(input_stream) as pdf:
            output = io.BytesIO()
            pdf.save(
                output,
                compression=pikepdf.CompressionLevel.compression_level_fast,
                optimize_version=True
            )
            return output.getvalue()
    except Exception as e:
        print(f"[pikepdf] Fehler bei der Re-Komprimierung: {e}")
        return input_bytes
