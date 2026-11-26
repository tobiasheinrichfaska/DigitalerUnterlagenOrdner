# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
from PIL import Image
import hashlib
import io
import logging
import threading
from dataclasses import dataclass
from typing import Tuple
from pypdf import PdfReader, PdfWriter
import pikepdf

from belegtool_compress import cpu, raster
from belegtool_compress.pixels import capped_dpi_for_size

logger = logging.getLogger("belegtool_compress")


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
        colorspace: Colorspace string.  "gray" = grayscale (smaller),
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
    # Guard against silent page loss: _render_pdf_as_images omits any page that fails to
    # render, so a smaller result could have *fewer* pages than the source. Never return a
    # truncated document — fall back to the original if the page count dropped.
    try:
        n_in = _strict_page_count(input_bytes)
        n_out = _strict_page_count(reencoded)
        if n_in == 0 or n_out < n_in:
            return input_bytes
    except Exception:
        return input_bytes
    # Otherwise return whichever is smaller: the re-encoded result or the original.
    return reencoded if len(reencoded) < len(input_bytes) else input_bytes


def _strict_page_count(data: bytes) -> int:
    """Page count that RAISES on unreadable input (callers treat that as 'do not compress')."""
    with pikepdf.open(io.BytesIO(data), suppress_warnings=True) as pdf:
        return len(pdf.pages)


class CompressionCancelled(Exception):
    """Raised through the page loop when the node being compressed is removed
    (split/deleted/merged), so the (wasted) work stops instead of running on."""


def compress_all_methods(
    input_bytes: bytes,
    dpi: int = DEFAULT_CONFIG.dpi,
    config: CompressionConfig = DEFAULT_CONFIG,
    cancel=None,
) -> dict:
    """Run every available compression method and return {method_name: bytes}.

    Only entries smaller than the input are included. The dict is sorted
    smallest-first so callers can pick dict[next(iter(...))] for the best result.

    The set of methods tried is taken from ``config.methods``; defaults are
    ("jpg", "jpg_color", "png", "pikepdf"). ``cancel`` is an optional predicate checked between
    methods and per page; if it returns True, ``CompressionCancelled`` is raised.
    """
    candidates = {}
    # Source page count, for the truncation guard below. If even counting fails,
    # the input is too broken to compress safely — offer nothing.
    try:
        n_pages = _strict_page_count(input_bytes)
    except Exception as e:
        logger.warning("Kompression übersprungen (Quelle nicht lesbar): %s", e)
        return {}
    if n_pages == 0:
        return {}  # nothing to compress (a page-less document is never "smaller")

    for method in config.methods:
        if cancel is not None and cancel():
            raise CompressionCancelled()
        try:
            if method == "pikepdf":
                result = recompress_with_pikepdf(input_bytes)
            else:
                result = _render_pdf_as_images(input_bytes, dpi=dpi, method=method,
                                               config=config, cancel=cancel)
                result = reencode_pdf_structure(result)
            # Never offer a truncated candidate: _render_pdf_as_images SKIPS a page
            # that fails to rasterize, so a "smaller" result can be smaller because
            # pages are MISSING. Applying it would silently lose the page — and on
            # reload the stored pdf_length would shift every following node's pages.
            n_out = _strict_page_count(result)
            if n_out != n_pages:
                logger.warning("Kompression '%s' verworfen: %d statt %d Seiten",
                               method, n_out, n_pages)
                continue
            if len(result) < len(input_bytes):
                candidates[method] = result
        except CompressionCancelled:
            raise
        except Exception as e:
            logger.warning("Kompression '%s' fehlgeschlagen: %s", method, e)

    return dict(sorted(candidates.items(), key=lambda kv: len(kv[1])))


# --- parallel page rendering ----------------------------------------------
# Compression rasterizes every page (the slow part). We spread that across a
# capped, below-normal-priority thread pool (terminal-server fair, see cpu.py).
# Each worker opens its own raster session over a contiguous page range and the image bytes are
# assembled back in page order → output is byte-identical to the sequential path. pdfium is not thread
# safe, so ``belegtool_compress.raster`` serialises every pdfium call under one process-wide lock
# (background priority: an interactive preview page overtakes this work). The pool therefore buys
# fairness (below-normal threads, the JPEG/PNG encoding overlaps the next render), not raw rasterizing
# throughput — which was GIL-limited (~1.2x) under PyMuPDF anyway.
# Only parallelize documents big enough to amortize the pool coordination; small and medium PDFs render
# inline (sequentially), which is plenty fast. One-line tunable.
_PARALLEL_MIN_PAGES = 50
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


def _render_one_page(doc, page_index, dpi, method, config, pil_mode):
    """Rasterize + encode a single page → (img_bytes, width, height). Pure: no shared state besides the
    rasterizer's own lock, so it is safe to run on a worker thread (with that thread's session ``doc``)."""
    page_w, page_h = doc.page_size(page_index)
    if config.max_width_pt is not None and page_w > config.max_width_pt:
        scale_factor = config.max_width_pt / page_w
        dpi_rel = int(dpi * scale_factor)
        target_width = config.max_width_pt
        target_height = page_h * scale_factor
    else:
        dpi_rel = dpi
        target_width = page_w
        target_height = page_h
    # Same per-page pixel budget as the host's preview renders (pixels.capped_dpi_for_size): the
    # width clamp alone leaves the height unbounded against an oversized MediaBox.
    dpi_rel = capped_dpi_for_size(page_w, page_h, dpi_rel)
    image = doc.render(page_index, dpi_rel, gray=(pil_mode == "L"))
    buf = io.BytesIO()
    if method in ("jpg", "jpg_color"):
        quality = config.jpeg_quality_color if method == "jpg_color" else config.jpeg_quality
        image.save(buf, format="JPEG", quality=quality)
    elif method == "png":
        image.save(buf, format="PNG", compress_level=config.png_compress_level)
    else:
        raise ValueError(f"Unbekannte Komprimierungsmethode: {method}")
    return buf.getvalue(), target_width, target_height


def _render_chunk(input_bytes, indices, dpi, method, config, pil_mode, cancel=None):
    """Render a contiguous range of pages on one worker, each chunk on its OWN raster session.
    Checks ``cancel`` per page so a removed node's compression stops promptly."""
    out = []
    with raster.open_pdf(input_bytes, background=True) as doc:
        for page_index in indices:
            if cancel is not None and cancel():
                raise CompressionCancelled()
            try:
                img, w, h = _render_one_page(doc, page_index, dpi, method, config, pil_mode)
                out.append((page_index, img, w, h))
            except CompressionCancelled:
                raise
            except Exception as e:
                logger.warning("Fehler bei Seite %d: %s", page_index, e)
    return out


def _render_pdf_as_images(
    input_bytes: bytes,
    dpi: int = DEFAULT_CONFIG.dpi,
    method: str = "jpg",
    config: CompressionConfig = DEFAULT_CONFIG,
    cancel=None,
) -> bytes:
    """Renders every page to an image.  Broken pages are skipped.

    Greyscale for "jpg"/"png"; colour (RGB) for "jpg_color".

    Pages wider than config.max_width_pt are scaled down to that width.
    The colorspace, JPEG quality, and PNG compression level are taken from
    ``config`` so that all magic numbers are centralised in CompressionConfig.
    """
    # "jpg_color" always renders colour, regardless of the config colorspace;
    # the other image methods follow config.colorspace (grayscale by default).
    if method == "jpg_color":
        pil_mode = "RGB"
    else:
        pil_mode = "L" if config.colorspace == "gray" else "RGB"

    with raster.open_pdf(input_bytes, background=True) as src:
        n_pages = src.page_count

    # rasterize+encode every page (the slow part) — across workers when it pays off
    workers = min(cpu.worker_count(), max(1, n_pages))
    if workers <= 1 or n_pages < _PARALLEL_MIN_PAGES:
        rendered = _render_chunk(input_bytes, range(n_pages), dpi, method, config, pil_mode, cancel)
    else:
        pool = _get_compress_pool()
        chunks = _contiguous_chunks(n_pages, workers)
        rendered = []
        futures = [pool.submit(_render_chunk, input_bytes, ch, dpi, method, config, pil_mode, cancel)
                   for ch in chunks]
        try:
            for fut in futures:
                rendered.extend(fut.result())  # CompressionCancelled propagates here
        except CompressionCancelled:
            for f in futures:
                f.cancel()  # stop siblings that haven't started instead of letting them run on
            raise

    # assemble sequentially in page order → byte-identical to the old serial path
    rendered.sort(key=lambda t: t[0])
    return _assemble_pdf(rendered)


def _assemble_pdf(rendered) -> bytes:
    """One page per ``(index, image_bytes, width_pt, height_pt)``, the image fitted
    (aspect kept, centred) into the page. Built with pikepdf: JPEG data is embedded as is
    (DCTDecode); 8-bit non-interlaced grey/RGB PNG data is embedded as its deflated IDAT
    stream with a PNG predictor (no decode/re-encode); anything else is decoded by Pillow
    and stored deflated."""
    pdf = pikepdf.Pdf.new()
    shared = {}  # identical page images (repeated blank/stamp pages) are stored once, as fitz did
    for _idx, img_bytes, target_width, target_height in rendered:
        key = hashlib.sha1(img_bytes).digest()
        if key not in shared:
            shared[key] = _image_xobject(pdf, img_bytes)
        xobj, px_w, px_h = shared[key]
        scale = min(target_width / px_w, target_height / px_h)
        dw, dh = px_w * scale, px_h * scale
        x, y = (target_width - dw) / 2.0, (target_height - dh) / 2.0
        content = "q %.6f 0 0 %.6f %.6f %.6f cm /Im0 Do Q" % (dw, dh, x, y)
        page = pikepdf.Dictionary(
            Type=pikepdf.Name.Page,
            MediaBox=pikepdf.Array([0, 0, float(target_width), float(target_height)]),
            Contents=pdf.make_stream(content.encode("ascii")),
            Resources=pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=xobj)),
        )
        pdf.pages.append(pikepdf.Page(page))
    out_buf = io.BytesIO()
    pdf.save(out_buf)
    return out_buf.getvalue()


def _png_idat(data: bytes):
    """``(width, height, colour_type, idat_bytes)`` of a PNG that can be embedded as is
    (8-bit grey/RGB, non-interlaced, no ancillary transparency), else ``None``."""
    import struct
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, hdr = 8, [], None
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype in (b"PLTE", b"tRNS"):
            return None
        elif ctype == b"IEND":
            break
    if hdr is None or not idat:
        return None
    w, h, depth, ctype_, _comp, _filt, interlace = hdr
    if depth != 8 or ctype_ not in (0, 2) or interlace != 0:
        return None
    return w, h, ctype_, b"".join(idat)


def _image_xobject(pdf, img_bytes: bytes):
    """PDF image XObject for encoded JPEG/PNG bytes -> ``(stream, px_width, px_height)``."""
    Name = pikepdf.Name
    with Image.open(io.BytesIO(img_bytes)) as im:
        fmt, mode, (px_w, px_h) = im.format, im.mode, im.size
        if fmt == "JPEG" and mode in ("L", "RGB"):
            stream = pikepdf.Stream(pdf, img_bytes)
            stream.Filter = Name.DCTDecode
            stream.ColorSpace = Name.DeviceGray if mode == "L" else Name.DeviceRGB
            stream.BitsPerComponent = 8
        else:
            png = _png_idat(img_bytes) if fmt == "PNG" else None
            if png is not None:
                _w, _h, ctype, idat = png
                colors = 1 if ctype == 0 else 3
                stream = pikepdf.Stream(pdf, idat)
                stream.Filter = Name.FlateDecode
                stream.DecodeParms = pikepdf.Dictionary(
                    Predictor=15, Colors=colors, BitsPerComponent=8, Columns=px_w)
                stream.ColorSpace = Name.DeviceGray if colors == 1 else Name.DeviceRGB
                stream.BitsPerComponent = 8
            else:
                # generic path: decode, flatten alpha onto white, store deflated raw samples
                import zlib
                if mode in ("LA", "RGBA", "P", "PA") or "transparency" in im.info:
                    rgba = im.convert("RGBA")
                    base = Image.new("RGB", rgba.size, (255, 255, 255))
                    base.paste(rgba, mask=rgba.getchannel("A"))
                    flat = base
                else:
                    flat = im.convert("L" if mode in ("L", "1", "I;16", "I", "F") else "RGB")
                stream = pikepdf.Stream(pdf, zlib.compress(flat.tobytes(), 6))
                stream.Filter = Name.FlateDecode
                stream.ColorSpace = Name.DeviceGray if flat.mode == "L" else Name.DeviceRGB
                stream.BitsPerComponent = 8
    stream.Type = Name.XObject
    stream.Subtype = Name.Image
    stream.Width = px_w
    stream.Height = px_h
    return stream, px_w, px_h


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
