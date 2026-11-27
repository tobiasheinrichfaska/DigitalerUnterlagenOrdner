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
        px = doc.render(0, 72, False).convert("L").getpixel((10, 10))
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
