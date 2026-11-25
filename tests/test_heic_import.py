"""Characterisation of the HEIC import path (UniversalImporter.convert).

Fixture ``tests/data/input/golden_heic.heic`` is synthetic (96x64 gradient and two
shapes drawn with Pillow, encoded once); no third-party image content. The test is
codec-agnostic on purpose: it must stay green across the pillow-heif -> pi-heif swap.
"""
import io
import os

import pytest

pytest.importorskip("fitz")
import fitz  # noqa: E402

from universal_importer import UniversalImporter  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "data", "input", "golden_heic.heic")
W, H = 96, 64


def _check(result):
    data = result.data.getvalue()
    assert data.lstrip().startswith(b"%PDF")
    doc = fitz.open(stream=data, filetype="pdf")
    assert doc.page_count == 1
    pix = doc[0].get_pixmap(dpi=72)
    assert pix.width > 0 and pix.height > 0
    # Page aspect ratio follows the image (96x64 = 3:2).
    assert abs(pix.width / pix.height - W / H) < 0.05
    # Pixels plausible: top half is the blue/red gradient, bottom-left the orange box.
    def px(x, y):
        return pix.pixel(int(x * pix.width / W), int(y * pix.height / H))
    r, g, b = px(5, 10)
    assert b > r + 100  # left edge of gradient: blue-ish
    r, g, b = px(90, 10)
    assert r > b + 100  # right edge: red-ish
    r, g, b = px(30, 48)
    assert r > 180 and b < 110  # orange rectangle
    # Embedded image keeps the source resolution.
    images = doc[0].get_images()
    assert len(images) == 1
    info = doc.extract_image(images[0][0])
    assert (info["width"], info["height"]) == (W, H)


def test_heic_path_to_pdf():
    _check(UniversalImporter.convert(FIXTURE))


def test_heic_bytes_to_pdf():
    with open(FIXTURE, "rb") as f:
        data = f.read()
    result = UniversalImporter.convert(data, name="Handyfoto.heic")
    assert result.name == "Handyfoto.heic"
    _check(result)
