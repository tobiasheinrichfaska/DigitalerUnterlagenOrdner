from pypdf import PdfReader
import io

from belegtool_compress.compress import compress_pdf_bytes
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
    from belegtool_compress import compress as cpb
    from belegtool_compress import pixels, raster
    monkeypatch.setattr(pixels, "MAX_RENDER_PIXELS", 250_000)
    doc = fitz.open()
    doc.new_page(width=595, height=14400)  # A4 width → no width clamp; giant height
    data = doc.tobytes()
    doc.close()
    with raster.open_pdf(data) as session:
        img, w, h = cpb._render_one_page(session, 0, 150, "jpg", cpb.DEFAULT_CONFIG, "L")
    with Image.open(io.BytesIO(img)) as im:
        assert im.width * im.height <= 250_000  # rendered small, not GBs
    assert (w, h) == (595, 14400)  # placement dims in the output PDF unchanged


def test_compress_all_methods_drops_candidates_that_lose_pages(monkeypatch):
    """H1 (audit 2026-11-03): a page that fails to rasterize is skipped with only a
    log line, so the 'compressed' variant silently loses that page — and on reload
    the fixed per-node pdf_length shifts every FOLLOWING document's pages. The live
    path (engine → compress_all_methods) must never offer a truncated candidate;
    the old guard lived only in the unused compress_pdf_bytes()."""
    from belegtool_compress import compress as cpb

    original = create_valid_pdf(pages=3)
    # Precondition against a vacuous pass: the fixture must actually produce at
    # least one render-based candidate (with a missing LFS sample the helper falls
    # back to blank pages, nothing is offered, and this test would prove nothing).
    baseline = cpb.compress_all_methods(original, dpi=100)
    assert any(m in baseline for m in ("jpg", "jpg_color", "png")), \
        "Fixture bietet keine Render-Variante an — LFS-Sample fehlt?"
    real_render = cpb._render_one_page

    def flaky(doc, page_index, *args, **kwargs):
        if page_index == 1:
            raise RuntimeError("Seite kaputt (Testfehler)")
        return real_render(doc, page_index, *args, **kwargs)

    monkeypatch.setattr(cpb, "_render_one_page", flaky)
    results = cpb.compress_all_methods(original, dpi=100)

    # pikepdf does not rasterize, so it may legitimately succeed; every
    # render-based candidate must be dropped, never offered truncated.
    for method, data in results.items():
        assert len(PdfReader(io.BytesIO(data)).pages) == 3, (
            f"Methode {method} liefert ein um Seiten gekürztes PDF")
