"""Robustness of the image -> PDF assembly for image kinds the compressor does not produce
itself (it always emits grey/RGB JPEG/PNG): alpha, palette, 16 bit, 1 bit, CMYK JPEG,
interlaced PNG. Green against the pikepdf implementation; against the former fitz one all
cases passed EXCEPT ``png-gray16`` (fitz rendered 16 bit grey PNGs as a black page) - a
deliberate improvement."""

import io

import fitz
import pikepdf
import pytest
from PIL import Image, ImageDraw

from belegtool_compress import compress as cmp


def _base():
    im = Image.new("RGB", (300, 200), (240, 240, 240))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 75, 50], fill=(0, 0, 0))
    d.rectangle([225, 150, 300, 200], fill=(200, 30, 30))
    return im


def _odd_images():
    base = _base()
    return {
        "png-rgba-opaque": ("PNG", base.convert("RGBA"), {}),
        "png-palette": ("PNG", base.convert("P", palette=Image.ADAPTIVE, colors=64), {}),
        "png-gray16": ("PNG", base.convert("I;16"), {}),
        "png-1bit": ("PNG", base.convert("1"), {}),
        "jpeg-cmyk": ("JPEG", base.convert("CMYK"), {}),
        "jpeg-progressive": ("JPEG", base, {"progressive": True}),
        "png-interlaced": ("PNG", base, {"interlace": 1}),
    }


@pytest.mark.parametrize("name", sorted(_odd_images()))
def test_assemble_handles_unusual_image_modes(name):
    fmt, img, kw = _odd_images()[name]
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kw)
    data = cmp._assemble_pdf([(0, buf.getvalue(), 300.0, 200.0)])
    with pikepdf.open(io.BytesIO(data)) as p:
        assert len(p.pages) == 1
        p.save(io.BytesIO())
    with fitz.open(stream=data, filetype="pdf") as d:
        pix = d[0].get_pixmap(dpi=72, colorspace=fitz.csGRAY)
        assert (pix.width, pix.height) == (300, 200)
        samples = pix.samples
    assert max(samples) - min(samples) > 100, "page is blank - image lost"


def test_png_pages_are_stored_deflated():
    """DELIBERATE DEVIATION (improvement): the fitz implementation stored PNG pages as
    uncompressed samples (800x600 grey -> ~480 KB even for a 1.6 KB PNG), so the 'png'
    method was practically never smaller than its source and never offered. The pikepdf
    assembly embeds the PNG's deflated IDAT data, so the PDF stays close to the PNG size."""
    img = Image.new("L", (800, 600), 240)
    ImageDraw.Draw(img).rectangle([100, 100, 300, 200], fill=0)
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    data = cmp._assemble_pdf([(0, buf.getvalue(), 595.0, 446.0)])
    assert len(data) < len(buf.getvalue()) * 1.5 + 2000, (len(data), len(buf.getvalue()))
