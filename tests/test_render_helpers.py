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
