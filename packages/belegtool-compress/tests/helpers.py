"""Test helper: a self-contained, compressible sample PDF (no external fixtures)."""

import io

import fitz
from PIL import Image


def create_valid_pdf(pages=1) -> bytes:
    """`pages` pages, each a large high-quality JPEG gradient, so lossy re-rendering at a
    lower DPI/quality produces a clearly smaller result."""
    doc = fitz.open()
    img = Image.new("RGB", (1240, 1754))
    px = img.load()
    for y in range(0, 1754):
        for x in range(0, 1240):
            px[x, y] = ((x * 255) // 1240, (y * 255) // 1754, ((x + y) * 7) % 256)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=98)
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(0, 0, 595, 842), stream=buf.getvalue())
    data = doc.tobytes(deflate=True)
    doc.close()
    return data
