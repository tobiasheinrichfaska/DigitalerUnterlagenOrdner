# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Characterisation of the image -> PDF assembly step of the compressor (PyMuPDF replacement,
step 1). Green against the fitz implementation first, kept green after the swap to
pikepdf. fitz is used HERE only as the independent oracle (rendering the result)."""

import io

import fitz
import pikepdf
import pytest
from pypdf import PdfReader
from PIL import Image, ImageChops, ImageDraw

from belegtool_compress import compress as cmp


def _image(mode, w=400, h=300):
    """Asymmetric test image: black block top-left, gradient, a grey bar bottom-right."""
    im = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w // 4, h // 4], fill=(0, 0, 0))
    d.rectangle([w * 3 // 4, h * 3 // 4, w, h], fill=(200, 30, 30))
    for x in range(w):
        d.line([x, h // 2, x, h // 2 + 20], fill=(x * 255 // w, 120, 255 - x * 255 // w))
    return im.convert(mode)


def _enc(im, fmt):
    buf = io.BytesIO()
    if fmt == "JPEG":
        im.save(buf, format="JPEG", quality=90)
    else:
        im.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def _render(pdf_bytes, page_no=0):
    with fitz.open(stream=pdf_bytes, filetype="pdf") as d:
        pix = d[page_no].get_pixmap(dpi=72, colorspace=fitz.csRGB)
        return Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("RGB")


def _expected(img, w_pt, h_pt):
    """What 'image fitted (aspect kept) and centred into the page' looks like at 72 dpi."""
    pw, ph = round(w_pt), round(h_pt)
    canvas = Image.new("RGB", (pw, ph), (255, 255, 255))
    scale = min(w_pt / img.width, h_pt / img.height)
    nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
    canvas.paste(img.convert("RGB").resize((nw, nh), Image.LANCZOS),
                 ((pw - nw) // 2, (ph - nh) // 2))
    return canvas


def _mean_diff(a, b):
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b).convert("L")
    return sum(diff.getdata()) / (a.width * a.height)


@pytest.mark.parametrize("mode", ["L", "RGB"])
@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
@pytest.mark.parametrize("page", [(595.0, 446.25), (595.0, 842.0), (300.5, 120.25)],
                         ids=["same-aspect", "tall-page-centred", "wide-page"])
def test_assembled_page_size_and_content(mode, fmt, page):
    img = _image(mode)
    data = cmp._assemble_pdf([(0, _enc(img, fmt), page[0], page[1])])
    assert data.startswith(b"%PDF")
    with pikepdf.open(io.BytesIO(data)) as p:
        assert len(p.pages) == 1
        box = [float(x) for x in p.pages[0].MediaBox]
        assert abs((box[2] - box[0]) - page[0]) <= 0.01
        assert abs((box[3] - box[1]) - page[1]) <= 0.01
    with fitz.open(stream=data, filetype="pdf") as d:
        assert abs(d[0].rect.width - page[0]) <= 0.01
        assert abs(d[0].rect.height - page[1]) <= 0.01
    got = _render(data)
    # orientation + placement + colour/grey fidelity (resampling differences tolerated)
    assert _mean_diff(got, _expected(img, *page)) < 8.0


def test_assemble_multiple_pages_in_given_order():
    a = _enc(_image("L", 200, 100), "JPEG")
    b = _enc(_image("RGB", 100, 200), "PNG")
    c = _enc(_image("L", 150, 150), "PNG")
    data = cmp._assemble_pdf([(0, a, 200.0, 100.0), (1, b, 100.0, 200.0), (2, c, 150.0, 150.0)])
    with pikepdf.open(io.BytesIO(data)) as p:
        sizes = [(float(pg.MediaBox[2]), float(pg.MediaBox[3])) for pg in p.pages]
    assert sizes == [(200.0, 100.0), (100.0, 200.0), (150.0, 150.0)]
    with fitz.open(stream=data, filetype="pdf") as d:
        assert d.page_count == 3


def test_assemble_is_valid_and_not_bloated():
    img = _image("L", 800, 600)
    raw = 800 * 600
    for fmt in ("JPEG", "PNG"):
        blob = _enc(img, fmt)
        data = cmp._assemble_pdf([(0, blob, 595.0, 446.0)])
        with pikepdf.open(io.BytesIO(data)) as p:
            p.save(io.BytesIO())  # qpdf walks + validates every reachable object
        PdfReader(io.BytesIO(data), strict=True)
        assert _render(data).size[0] > 0
        if fmt == "JPEG":
            # DCT data is embedded as is, never re-encoded
            assert len(data) < len(blob) * 1.25 + 2000, (len(data), len(blob))
        else:
            # never larger than the raw samples (the fitz implementation stored PNG pages
            # as UNCOMPRESSED samples ~ raw; the pikepdf one embeds the deflated data and is
            # far smaller - see test_png_pages_are_stored_deflated)
            assert len(data) <= raw + 5000, (len(data), raw)


def _two_pages():
    import sys
    pdf = pikepdf.Pdf.new()
    for _ in range(2):
        pdf.add_blank_page(page_size=(595, 842))
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def test_render_pdf_as_images_keeps_pages_and_clamped_sizes():
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(595, 842))
    pdf.add_blank_page(page_size=(842, 595))  # wider than max_width_pt -> scaled to 595 wide
    buf = io.BytesIO()
    pdf.save(buf)
    for method in ("jpg", "jpg_color", "png"):
        out = cmp._render_pdf_as_images(buf.getvalue(), dpi=72, method=method)
        with pikepdf.open(io.BytesIO(out)) as p:
            assert len(p.pages) == 2
            w1 = float(p.pages[1].MediaBox[2]) - float(p.pages[1].MediaBox[0])
            h1 = float(p.pages[1].MediaBox[3]) - float(p.pages[1].MediaBox[1])
        assert abs(w1 - 595.0) <= 0.01
        assert abs(h1 - 595.0 * 595 / 842) <= 0.01


def test_compress_all_methods_survives_garbage_and_empty():
    assert cmp.compress_all_methods(b"not a pdf") == {}
    pdf = pikepdf.Pdf.new()
    buf = io.BytesIO()
    pdf.save(buf)
    res = cmp.compress_all_methods(buf.getvalue())
    assert res == {}
