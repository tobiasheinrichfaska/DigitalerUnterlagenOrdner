"""Generate the input PDF fixtures the test suite expects.

The tests render-compress these PDFs at 150 DPI grayscale (JPEG q60) and assert
that compression yields a *smaller* result (``is_compressed`` / ``dpi_current``).
For that to hold, each page must embed a high-resolution, richly detailed image
so the original is clearly larger than the re-encoded version.

Run once from the project root:
    python tests/make_fixtures.py

Required fixtures (see tests/*.py):
  - sample.pdf          (multi-page)  helpers.create_valid_pdf, test_pdf_node_preview_lazy
  - compress_sample.pdf               test_pdf_node_compression, foldermerge("compress")
  - split_sample.pdf    (multi-page)  test_pdf_node_split, foldermerge("split")
  - merge1_a.pdf / merge1_b.pdf       test_pdf_node_merge_files (merge<ID>), foldermerge("merge")
"""

import io
import math
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

# A4 in points and the DPI we render the *source* image at (well above the
# 150 DPI the compressor uses, so the original is the larger of the two).
A4_W_PT, A4_H_PT = 595.0, 842.0
# The compressor re-renders at 150 DPI grayscale (JPEG q60). Source pages are
# kept at the same 150 DPI but full RGB and higher quality, so the original
# stays comfortably larger than the compressed result while keeping the
# committed fixtures small.
SOURCE_DPI = 150
PX_W = int(A4_W_PT / 72 * SOURCE_DPI)
PX_H = int(A4_H_PT / 72 * SOURCE_DPI)

INPUT_DIR = Path(__file__).parent / "data" / "input"


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _page_image(page_no: int, title: str) -> Image.Image:
    """A detailed, document-like RGB page: gradient, shapes, ruled text rows.

    Detailed enough to look like a scanned receipt, structured enough that the
    150-DPI grayscale q60 re-encode comes out clearly smaller than this source.
    """
    img = Image.new("RGB", (PX_W, PX_H), "white")
    px = img.load()
    # Diagonal gradient background (forces real tonal data into the image).
    for y in range(PX_H):
        for x in range(0, PX_W, 3):
            v = (math.sin((x + y) / 90.0) + 1) * 60
            c = int(190 + v % 60)
            px[x, y] = (c, c, min(255, c + 12))
            if x + 1 < PX_W:
                px[x + 1, y] = (c, c, min(255, c + 12))
            if x + 2 < PX_W:
                px[x + 2, y] = (c, c, min(255, c + 12))

    d = ImageDraw.Draw(img)
    big, mid, small = _font(72), _font(40), _font(30)

    d.rectangle([60, 60, PX_W - 60, 200], fill=(40, 70, 120))
    d.text((90, 95), f"{title}", font=big, fill="white")

    d.rectangle([60, 240, PX_W - 60, 360], outline=(40, 70, 120), width=4)
    d.text((90, 270), f"Beleg-Nr. 2023-{page_no:04d}   Seite {page_no}",
           font=mid, fill=(20, 20, 20))

    # Ruled rows of "line items" — lots of edges/text for the compressor to chew.
    y = 420
    for i in range(28):
        d.line([80, y, PX_W - 80, y], fill=(150, 150, 150), width=2)
        d.text((100, y + 8),
                f"Position {i + 1:02d}  Artikel {(page_no * 37 + i * 13) % 9999:04d}  "
                f"Menge {1 + i % 7}  EUR {((i + 1) * 4.27 + page_no):8.2f}",
                font=small, fill=(15, 15, 15))
        y += 58

    d.rectangle([80, y + 20, PX_W - 80, y + 120], fill=(225, 235, 245),
                outline=(40, 70, 120), width=3)
    d.text((100, y + 50), f"Summe Seite {page_no}: EUR {page_no * 318.55:10.2f}",
           font=mid, fill=(10, 10, 10))
    return img


def _build_pdf(path: Path, n_pages: int, title: str) -> None:
    doc = fitz.open()
    for p in range(1, n_pages + 1):
        image = _page_image(p, title)
        buf = io.BytesIO()
        # Full-colour, good quality so the source PDF stays larger than the
        # compressor's 150-DPI grayscale q60 pass.
        image.save(buf, format="JPEG", quality=85)
        page = doc.new_page(width=A4_W_PT, height=A4_H_PT)
        page.insert_image(fitz.Rect(0, 0, A4_W_PT, A4_H_PT), stream=buf.getvalue())
    doc.save(path, deflate=True)
    doc.close()


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = [
        ("sample.pdf", 3, "Sample Beleg"),
        ("compress_sample.pdf", 2, "Kompression Testbeleg"),
        ("split_sample.pdf", 3, "Split Testbeleg"),
        ("merge1_a.pdf", 1, "Merge Gruppe 1 - Teil A"),
        ("merge1_b.pdf", 2, "Merge Gruppe 1 - Teil B"),
    ]
    for name, pages, title in fixtures:
        out = INPUT_DIR / name
        _build_pdf(out, pages, title)
        print(f"  {name:24s} {pages} page(s)  {out.stat().st_size / 1024:8.1f} KiB")


if __name__ == "__main__":
    main()
