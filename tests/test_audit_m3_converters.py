# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit m3 Y-3/Y-4/Y-5: converter regressions (Windows COM modules stubbed so this runs anywhere)."""
import base64
import io
import sys
import types

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

import pypdf  # noqa: E402
from PIL import Image  # noqa: E402

from universal_importer import converters  # noqa: E402


def _text(conv):
    return "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(conv.data.getvalue())).pages)


def test_y3_16bit_grey_png_not_blown_out(tmp_path):
    img = Image.new("I;16", (64, 64), 32768)  # mid grey
    p = tmp_path / "g.png"
    img.save(p)
    conv = converters.standard_image(str(p))
    from belegtool_compress import raster
    doc = raster.open_pdf(conv.data.getvalue())
    try:
        px = doc.render(0, 72, False).convert("L").getpixel((297, 420))  # page centre (A4, image centred)
    finally:
        doc.close()
    assert 100 < px < 160


def test_y4_tabs_expanded_and_unsupported_chars_not_boxes():
    t = _text(converters.txt_to_pdf("a\tb\nПривет Łódź"))
    assert "■" not in t and "\t" not in t
    assert "a" in t and "b" in t


def test_y4_html_unsupported_chars_not_boxes():
    t = _text(converters.html_to_pdf("<p>Привет Łódź</p>"))
    assert "■" not in t


def test_y5_empty_svg_data_uri_degrades():
    svg = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>').decode()
    conv = converters.html_to_pdf(f'<p>hi</p><img src="data:image/svg+xml;base64,{svg}">')
    assert conv.data.getvalue().startswith(b"%PDF")


# --- Y-1 / Y-2: image import -> A4 page, lossless stays lossless ---------------

def _page_info(conv):
    import pikepdf
    with pikepdf.open(io.BytesIO(conv.data.getvalue())) as pdf:
        pg = pdf.pages[0]
        box = [float(x) for x in pg.MediaBox]
        im = next(iter(pg.Resources.XObject.values()))
        return box[2] - box[0], box[3] - box[1], str(im.get("/Filter")), len(pdf.pages)


def test_y1_portrait_300dpi_scan_is_a4(tmp_path):
    p = tmp_path / "s.png"
    Image.new("RGB", (2480, 3508), "white").save(p, dpi=(300, 300))
    w, h, _, n = _page_info(converters.standard_image(str(p)))
    assert n == 1 and abs(w - 595.28) < 0.1 and abs(h - 841.89) < 0.1


def test_y1_landscape_photo_is_landscape_a4_and_fits_centred(tmp_path):
    p = tmp_path / "f.jpg"
    Image.new("RGB", (4000, 3000), "red").save(p)
    conv = converters.standard_image(str(p))
    w, h, _, _ = _page_info(conv)
    assert abs(w - 841.89) < 0.1 and abs(h - 595.28) < 0.1
    from belegtool_compress import raster
    doc = raster.open_pdf(conv.data.getvalue())
    try:
        im = doc.render(0, 72, False).convert("RGB")
    finally:
        doc.close()
    # 4:3 image on 1.414:1 page -> full height, white side margins, red centre
    assert im.getpixel((2, 300)) == (255, 255, 255)
    assert im.getpixel((420, 300))[0] > 200 and im.getpixel((420, 300))[1] < 50


def test_y1_tiny_image_scaled_up_without_distortion(tmp_path):
    p = tmp_path / "t.png"
    Image.new("RGB", (100, 50), "blue").save(p)
    w, h, _, _ = _page_info(converters.standard_image(str(p)))
    assert abs(w - 841.89) < 0.1 and abs(h - 595.28) < 0.1


def test_y2_png_stays_lossless(tmp_path):
    import random
    random.seed(1)
    src = Image.new("RGB", (64, 64))
    src.putdata([(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(64 * 64)])
    p = tmp_path / "n.png"
    src.save(p)
    conv = converters.standard_image(str(p))
    assert "DCT" not in _page_info(conv)[2]
    import pikepdf
    with pikepdf.open(io.BytesIO(conv.data.getvalue())) as pdf:
        im = pikepdf.PdfImage(next(iter(pdf.pages[0].Resources.XObject.values()))).as_pil_image().convert("RGB")
    assert list(im.getdata()) == list(src.getdata())


def test_y2_jpeg_embedded_without_reencoding(tmp_path):
    p = tmp_path / "j.jpg"
    Image.new("RGB", (300, 200), (10, 200, 30)).save(p, quality=90)
    conv = converters.standard_image(str(p))
    assert "DCT" in _page_info(conv)[2]
    assert p.read_bytes() in conv.data.getvalue()


def test_y2_alpha_png_over_white_lossless(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(p)
    conv = converters.standard_image(str(p))
    assert "DCT" not in _page_info(conv)[2]
