import fitz
from PIL import Image
import io
from pypdf import PdfReader, PdfWriter
import pikepdf
from log_config import logger


def compress_pdf_bytes(input_bytes: bytes, dpi: int = 150, method: str = "jpg") -> bytes:
    """Render-based compression followed by structural re-encode. Returns the smaller result."""
    rendered = _render_pdf_as_images(input_bytes, dpi=dpi, method=method)
    reencoded = reencode_pdf_structure(rendered)
    return reencoded


def compress_all_methods(input_bytes: bytes, dpi: int = 150) -> dict:
    """Run every available compression method and return {method_name: bytes}.

    Only entries smaller than the input are included. The dict is sorted
    smallest-first so callers can pick dict[next(iter(...))] for the best result.
    """
    candidates = {}

    for method in ("jpg", "png"):
        try:
            result = compress_pdf_bytes(input_bytes, dpi=dpi, method=method)
            candidates[method] = result
        except Exception as e:
            logger.warning("Kompression '%s' fehlgeschlagen: %s", method, e)

    try:
        result = recompress_with_pikepdf(input_bytes)
        candidates["pikepdf"] = result
    except Exception as e:
        logger.warning("Kompression 'pikepdf' fehlgeschlagen: %s", e)

    return dict(sorted(candidates.items(), key=lambda kv: len(kv[1])))


def _render_pdf_as_images(input_bytes: bytes, dpi: int = 150, method: str = "jpg") -> bytes:
    """Renders every page as a greyscale image. Broken pages are skipped."""
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
            logger.warning("Fehler bei Seite %d: %s", page_index, e)
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
        logger.warning("PDF-Reencode fehlgeschlagen: %s", e)
        return pdf_bytes


def recompress_with_pikepdf(input_bytes: bytes) -> bytes:
    """Structurally recompresses a PDF using pikepdf (no image re-rendering)."""
    try:
        with pikepdf.open(io.BytesIO(input_bytes)) as pdf:
            output = io.BytesIO()
            pdf.save(output, compress_streams=True, recompress_flate=True)
            return output.getvalue()
    except Exception as e:
        logger.warning("pikepdf-Rekomprimierung fehlgeschlagen: %s", e)
        return input_bytes
