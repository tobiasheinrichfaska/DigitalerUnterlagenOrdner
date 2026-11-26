# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""The 'jpg_color' variant must surface through the engine (needs core.engine -> host repo)."""

import io

import fitz
from PIL import Image


def _colorful_pdf(pages=1) -> bytes:
    """A PDF whose pages carry strong, distinct RGB regions."""
    doc = fitz.open()
    for _ in range(pages):
        img = Image.new("RGB", (600, 800))
        px = img.load()
        for y in range(800):
            for x in range(600):
                px[x, y] = ((x * 255) // 600, (y * 255) // 800, 128)  # R,G vary; B fixed
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        page = doc.new_page(width=300, height=400)
        page.insert_image(fitz.Rect(0, 0, 300, 400), stream=buf.getvalue())
    data = doc.tobytes(deflate=True)
    doc.close()
    return data


def _is_grayscale(pdf_bytes: bytes) -> bool:
    """True if every sampled pixel has R == G == B."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(dpi=72, colorspace=fitz.csRGB)
    img = Image.open(io.BytesIO(pix.tobytes("ppm"))).convert("RGB")
    doc.close()
    w, h = img.size
    for x in range(0, w, 40):
        for y in range(0, h, 40):
            r, g, b = img.getpixel((x, y))
            if abs(r - g) > 6 or abs(g - b) > 6:
                return False
    return True


def test_engine_exposes_jpg_color():
    """The variant must surface through the engine the UI/api use."""
    from core.engine import RealEngine

    src = _colorful_pdf(pages=2)
    eng = RealEngine()
    methods = eng.compress_methods(src, dpi=150)
    assert "jpg_color" in methods
    out = eng.compress(src, dpi=150, method="jpg_color")
    assert out and not _is_grayscale(out)
