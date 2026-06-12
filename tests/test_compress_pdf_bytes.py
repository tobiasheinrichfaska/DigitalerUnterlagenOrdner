from pypdf import PdfReader
import io

from formats.compress_pdf_bytes import compress_pdf_bytes
from helpers import create_valid_pdf


def test_compress_pdf_bytes_returns_valid_smaller_pdf():
    """compress_pdf_bytes must return a valid PDF no larger than the input."""
    original = create_valid_pdf(pages=2)  # real, compressible sample content

    result = compress_pdf_bytes(original, dpi=150)

    assert isinstance(result, bytes)
    assert result.startswith(b"%PDF"), "result is not a PDF"
    assert len(result) <= len(original), "compression must never grow the file"
    # Result is structurally readable and preserves the page count.
    assert len(PdfReader(io.BytesIO(result)).pages) == 2


def test_compress_pdf_bytes_keeps_original_when_no_gain():
    """A tiny PDF that cannot shrink is returned unchanged (never larger)."""
    tiny = create_valid_pdf(pages=1)
    result = compress_pdf_bytes(tiny, dpi=72)
    assert isinstance(result, bytes)
    assert len(result) <= len(tiny)


def test_compress_render_giant_page_is_bounded(monkeypatch):
    """The compress raster path enforces the same per-page pixel budget as the
    preview renders: the width clamp alone leaves a TALL MediaBox unbounded
    (legal width × hostile height), reached automatically via the proactive
    compress sweep on open (audit 2026-06-12)."""
    import fitz
    from PIL import Image
    from formats import compress_pdf_bytes as cpb
    from services import render
    monkeypatch.setattr(render, "MAX_RENDER_PIXELS", 250_000)
    doc = fitz.open()
    doc.new_page(width=595, height=14400)  # A4 width → no width clamp; giant height
    try:
        img, w, h = cpb._render_one_page(doc, 0, 150, "jpg",
                                         cpb.DEFAULT_CONFIG, fitz.csGRAY, "L")
        with Image.open(io.BytesIO(img)) as im:
            assert im.width * im.height <= 250_000  # rendered small, not GBs
        assert (w, h) == (595, 14400)  # placement dims in the output PDF unchanged
    finally:
        doc.close()
