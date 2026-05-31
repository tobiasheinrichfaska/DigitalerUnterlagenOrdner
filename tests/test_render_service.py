"""Tests for the headless preview-render service (services/render.py)."""

import io

from PIL import Image

from services.render import render_pdf_to_images, render_pdf_to_pngs
from helpers import create_valid_pdf

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_render_images_one_per_page():
    data = create_valid_pdf(pages=2)
    imgs = render_pdf_to_images(data)
    assert len(imgs) == 2
    assert all(isinstance(i, Image.Image) and i.mode == "RGB" for i in imgs)


def test_render_pngs_one_per_page():
    data = create_valid_pdf(pages=2)
    pngs = render_pdf_to_pngs(data)
    assert len(pngs) == 2
    assert all(isinstance(p, bytes) and p.startswith(PNG_SIGNATURE) for p in pngs)
    # PNGs are decodable back to images.
    assert Image.open(io.BytesIO(pngs[0])).size[0] > 0


def test_render_accepts_bytesio():
    imgs = render_pdf_to_images(io.BytesIO(create_valid_pdf(pages=1)))
    assert len(imgs) == 1


def test_render_invalid_inputs_return_empty():
    assert render_pdf_to_images(None) == []
    assert render_pdf_to_images(b"") == []
    assert render_pdf_to_images(b"not a pdf") == []
    assert render_pdf_to_pngs(None) == []


def test_higher_dpi_yields_larger_image():
    data = create_valid_pdf(pages=1)
    small = render_pdf_to_images(data, dpi=72)[0]
    large = render_pdf_to_images(data, dpi=150)[0]
    assert large.width > small.width
