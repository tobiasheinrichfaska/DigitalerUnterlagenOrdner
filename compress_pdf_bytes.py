import fitz
from PIL import Image
import io
import threading
from dataclasses import dataclass
from typing import Tuple
from pypdf import PdfReader, PdfWriter
import pikepdf
from log_config import logger
from services import cpu


@dataclass(frozen=True)
class CompressionConfig:
    """Central configuration for all PDF compression parameters.

    All hard-coded constants that previously lived scattered across
    compress_pdf_bytes.py are collected here.  The defaults reproduce
    the historical behaviour exactly so that existing callers are
    unaffected.

    Attributes:
        dpi: Default render DPI for image-based methods (jpg / png).
        jpeg_quality: JPEG quality (0–95).  Higher = better quality, larger file.
        png_compress_level: PNG deflate level (0–9).
        colorspace: Fitz colorspace string.  "gray" = grayscale (smaller),
            "rgb" = colour (larger but faithful).
        max_width_pt: Pages wider than this are scaled down to this width
            before rendering.  Set to None to disable downscaling.
        methods: Tuple of method keys tried by compress_all_methods.
    """
    dpi: int = 150
    jpeg_quality: int = 60        # grayscale JPEG ("jpg")
    jpeg_quality_color: int = 75  # colour JPEG ("jpg_color") — a touch higher
    png_compress_level: int = 6
    colorspace: str = "gray"
    max_width_pt: float = 595.0   # A4 width in points
    # "jpg"/"png" render grayscale; "jpg_color" keeps colour; "pikepdf" is
    # structural-only (no re-render, colour preserved).
    methods: Tuple[str, ...] = ("jpg", "jpg_color", "png", "pikepdf")


# Module-level default used by all public entry points.
DEFAULT_CONFIG = CompressionConfig()


def compress_pdf_bytes(input_bytes: bytes, dpi: int = 150, method: str = "jpg") -> bytes:
    """Render-based compression followed by structural re-encode.

    Renders every page at the given DPI using ``method`` ("jpg" or "png"),
    then re-encodes the PDF structure with pypdf.  Returns the smaller of
    the compressed result and the original input so that callers always get
    at most the same size back.

    Valid method values: "jpg" (lossy JPEG, grayscale), "png" (PNG, grayscale).
    """
    rendered = _render_pdf_as_images(input_bytes, dpi=dpi, method=method)
    reencoded = reencode_pdf_structure(rendered)
    # Always return whichever is smaller: the re-encoded result or the original.
    return reencoded if len(reencoded) < len(input_bytes) else input_bytes


def compress_all_methods(
    input_bytes: bytes,
    dpi: int = DEFAULT_CONFIG.dpi,
    config: CompressionConfig = DEFAULT_CONFIG,
) -> dict:
    """Run every available compression method and return {method_name: bytes}.

    Only entries smaller than the input are included. The dict is sorted
    smallest-first so callers can pick dict[next(iter(...))] for the best result.

    The set of methods tried is taken from ``config.methods``; defaults are
    ("jpg", "png", "pikepdf").
    """
    candidates = {}

    for method in config.methods:
        try:
            if method == "pikepdf":
                result = recompress_with_pikepdf(input_bytes)
            else:
                result = _render_pdf_as_images(input_bytes, dpi=dpi, method=method, config=config)
                result = reencode_pdf_structure(result)
            if len(result) < len(input_bytes):
                candidates[method] = result
        except Exception as e:
            logger.warning("Kompression '%s' fehlgeschlagen: %s", method, e)

    return dict(sorted(candidates.items(), key=lambda kv: len(kv[1])))


# --- parallel page rendering ----------------------------------------------
# Compression rasterizes every page (the slow part). We spread that across a
# capped, below-normal-priority thread pool (terminal-server fair, see services/cpu).
# PyMuPDF 1.26 renders concurrently as long as each thread uses its OWN Document,
# so each worker opens its own doc over a contiguous page range; the image bytes
# are deterministic and assembled back in page order → output stays byte-identical
# to the old sequential path.
# Only parallelize documents big enough to amortize the pool coordination — small
# PDFs render inline (sequentially), which is plenty fast and keeps timing simple.
_PARALLEL_MIN_PAGES = 8
_compress_pool = None
_compress_pool_lock = threading.Lock()


def _get_compress_pool():
    global _compress_pool
    if _compress_pool is None:
        with _compress_pool_lock:
            if _compress_pool is None:
                from concurrent.futures import ThreadPoolExecutor
                _compress_pool = ThreadPoolExecutor(
                    max_workers=cpu.worker_count(),
                    initializer=cpu.set_current_thread_below_normal,
                    thread_name_prefix="compress-pool",
                )
    return _compress_pool


def _contiguous_chunks(n: int, k: int):
    """Split range(n) into <=k contiguous index lists (keeps page locality)."""
    size = (n + k - 1) // k
    return [list(range(i, min(i + size, n))) for i in range(0, n, size)]


def _render_one_page(doc, page_index, dpi, method, config, cs, pil_mode):
    """Rasterize + encode a single page → (img_bytes, width, height). Pure: no
    shared state, so it is safe to run on a worker thread (with that thread's doc)."""
    page = doc.load_page(page_index)
    if config.max_width_pt is not None and page.rect.width >= config.max_width_pt:
        scale_factor = config.max_width_pt / page.rect.width
        dpi_rel = int(dpi * scale_factor)
        target_width = config.max_width_pt
        target_height = page.rect.height * scale_factor
    else:
        dpi_rel = dpi
        target_width = page.rect.width
        target_height = page.rect.height
    pix = page.get_pixmap(dpi=dpi_rel, colorspace=cs)
    image = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert(pil_mode)
    buf = io.BytesIO()
    if method in ("jpg", "jpg_color"):
        quality = config.jpeg_quality_color if method == "jpg_color" else config.jpeg_quality
        image.save(buf, format="JPEG", quality=quality)
    elif method == "png":
        image.save(buf, format="PNG", compress_level=config.png_compress_level)
    else:
        raise ValueError(f"Unbekannte Komprimierungsmethode: {method}")
    return buf.getvalue(), target_width, target_height


def _render_chunk(input_bytes, indices, dpi, method, config, cs, pil_mode):
    """Render a contiguous range of pages on one worker, each on its OWN doc."""
    doc = fitz.open(stream=input_bytes, filetype="pdf")
    out = []
    try:
        for page_index in indices:
            try:
                img, w, h = _render_one_page(doc, page_index, dpi, method, config, cs, pil_mode)
                out.append((page_index, img, w, h))
            except Exception as e:
                logger.warning("Fehler bei Seite %d: %s", page_index, e)
    finally:
        doc.close()
    return out


def _render_pdf_as_images(
    input_bytes: bytes,
    dpi: int = DEFAULT_CONFIG.dpi,
    method: str = "jpg",
    config: CompressionConfig = DEFAULT_CONFIG,
) -> bytes:
    """Renders every page as a greyscale image.  Broken pages are skipped.

    Pages wider than config.max_width_pt are scaled down to that width.
    The colorspace, JPEG quality, and PNG compression level are taken from
    ``config`` so that all magic numbers are centralised in CompressionConfig.
    """
    # "jpg_color" always renders colour, regardless of the config colorspace;
    # the other image methods follow config.colorspace (grayscale by default).
    if method == "jpg_color":
        cs, pil_mode = fitz.csRGB, "RGB"
    else:
        cs = fitz.csGRAY if config.colorspace == "gray" else fitz.csRGB
        pil_mode = "L" if config.colorspace == "gray" else "RGB"

    with fitz.open(stream=input_bytes, filetype="pdf") as src:
        n_pages = src.page_count

    # rasterize+encode every page (the slow part) — across workers when it pays off
    workers = min(cpu.worker_count(), max(1, n_pages))
    if workers <= 1 or n_pages < _PARALLEL_MIN_PAGES:
        rendered = _render_chunk(input_bytes, range(n_pages), dpi, method, config, cs, pil_mode)
    else:
        pool = _get_compress_pool()
        chunks = _contiguous_chunks(n_pages, workers)
        rendered = []
        for fut in [pool.submit(_render_chunk, input_bytes, ch, dpi, method, config, cs, pil_mode)
                    for ch in chunks]:
            rendered.extend(fut.result())

    # assemble sequentially in page order → byte-identical to the old serial path
    rendered.sort(key=lambda t: t[0])
    output_pdf = fitz.open()
    for _idx, img_bytes, target_width, target_height in rendered:
        rect = fitz.Rect(0, 0, target_width, target_height)
        img_page = output_pdf.new_page(width=target_width, height=target_height)
        img_page.insert_image(rect, stream=img_bytes, keep_proportion=True)

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
