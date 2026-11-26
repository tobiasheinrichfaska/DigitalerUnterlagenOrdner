"""Single-page render + cheap metadata helpers (windowed-cache primitives)."""

from helpers import create_valid_pdf
from services.render import page_count, page_dims, render_page


def test_page_count():
    assert page_count(create_valid_pdf(pages=3)) == 3
    assert page_count(b"") == 0
    assert page_count(None) == 0


def test_render_page_returns_png_bytes():
    data = create_valid_pdf(pages=2)
    png = render_page(data, 0, dpi=72)
    assert png.startswith(b"\x89PNG")


def test_render_page_out_of_range_and_empty():
    data = create_valid_pdf(pages=2)
    assert render_page(data, 5, dpi=72) == b""   # past the end
    assert render_page(data, -1, dpi=72) == b""
    assert render_page(b"", 0) == b""
    assert render_page(None, 0) == b""


def test_page_dims():
    dims = page_dims(create_valid_pdf(pages=2))
    assert len(dims) == 2
    assert all(w > 0 and h > 0 for w, h in dims)
    assert page_dims(b"") == []


# --- oversized-page pixel budget (DoS guard) --------------------------------
class _FakePage:
    class _Rect:
        def __init__(self, w, h):
            self.width, self.height = w, h

    def __init__(self, w, h):
        self.rect = self._Rect(w, h)


def test_capped_dpi_leaves_normal_pages_alone():
    from services.render import _capped_dpi
    assert _capped_dpi(_FakePage(595, 842), 300) == 300  # A4 at max slider DPI


def test_capped_dpi_clamps_giant_mediabox():
    from services import render
    page = _FakePage(14400, 14400)  # PDF max page size (200 × 200 in)
    dpi = render._capped_dpi(page, 100)
    assert dpi < 100
    px = (14400 * dpi / 72.0) * (14400 * dpi / 72.0)
    assert px <= render.MAX_RENDER_PIXELS


def test_render_page_giant_mediabox_is_bounded(monkeypatch):
    # end to end: a giant page renders a SMALL image instead of allocating GBs
    import io
    import fitz
    from PIL import Image
    from services import render
    monkeypatch.setattr(render, "MAX_RENDER_PIXELS", 250_000)
    doc = fitz.open()
    doc.new_page(width=14400, height=14400)
    data = doc.tobytes()
    doc.close()
    png = render.render_page(data, 0, dpi=100)
    assert png.startswith(b"\x89PNG")
    with Image.open(io.BytesIO(png)) as im:
        assert im.width * im.height <= 250_000


# --- rasterizer swap (pdfium): geometry the host-facing render_page must keep honouring -------------------
def _png_size(png):
    import io
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        return im.size


def test_render_page_honours_rotate_and_userunit():
    from pdf_synth import make_pdf
    assert _png_size(render_page(make_pdf([{"rotate": 90}]), 0, dpi=72)) == (842, 595)
    # /UserUnit 2: pdfium alone would ignore it (595x842); MuPDF/Acrobat give 2x
    assert _png_size(render_page(make_pdf([{"userunit": 2.0}]), 0, dpi=72)) == (1190, 1684)


def test_render_pdf_to_pngs_one_png_per_page_and_garbage_is_empty():
    from pdf_synth import make_pdf
    from services.render import render_pdf_to_pngs
    pngs = render_pdf_to_pngs(make_pdf(pages=3), dpi=50)
    assert len(pngs) == 3 and all(p.startswith(b"\x89PNG") for p in pngs)
    assert render_pdf_to_pngs(b"kein pdf") == []
