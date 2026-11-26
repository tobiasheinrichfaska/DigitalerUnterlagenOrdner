# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Smoke test of the SHIPPED dependency set: runs with only requirements.txt installed (no PyMuPDF).

    python scripts/smoke_no_pymupdf.py        # exit 0 = preview render + compression work without fitz

Used by CI (job ``no-pymupdf-runtime``) and the Windows runbook (docs/windows-pc-testlauf.md). It proves that
rasterizing (preview, compression variants) goes through pypdfium2 alone and that PyMuPDF is really absent.
"""
import importlib.util
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    for mod in ("fitz", "pymupdf"):
        if importlib.util.find_spec(mod) is not None:
            print(f"FEHLER: {mod} ist installiert - dieser Test gilt dem ausgelieferten Satz ohne PyMuPDF")
            return 1

    import pikepdf
    from PIL import Image

    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                BaseFont=pikepdf.Name.Helvetica))
    for i in range(2):
        page = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Page, MediaBox=pikepdf.Array([0, 0, 595, 842]),
            Resources=pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font)),
            Contents=pdf.make_stream(b"1 0 0 rg 0 0 100 100 re f BT /F1 24 Tf 0 g 72 700 Td (Smoke %d) Tj ET" % i)))
        pdf.pages.append(pikepdf.Page(page))
    buf = io.BytesIO()
    pdf.save(buf)
    data = buf.getvalue()

    # a compressible "scan" page (large high-quality JPEG) for the compression path
    img = Image.new("RGB", (1240, 1754))
    px = img.load()
    for y in range(1754):
        for x in range(1240):
            px[x, y] = ((x * 255) // 1240, (y * 255) // 1754, ((x + y) * 7) % 256)
    jpg = io.BytesIO()
    img.save(jpg, "JPEG", quality=98)
    scan = pikepdf.Pdf.new()
    xobj = pikepdf.Stream(scan, jpg.getvalue())
    xobj.Type, xobj.Subtype, xobj.Filter = pikepdf.Name.XObject, pikepdf.Name.Image, pikepdf.Name.DCTDecode
    xobj.Width, xobj.Height, xobj.ColorSpace, xobj.BitsPerComponent = 1240, 1754, pikepdf.Name.DeviceRGB, 8
    scan.pages.append(pikepdf.Page(scan.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Page, MediaBox=pikepdf.Array([0, 0, 595, 842]),
        Resources=pikepdf.Dictionary(XObject=pikepdf.Dictionary(Im0=xobj)),
        Contents=scan.make_stream(b"q 595 0 0 842 0 0 cm /Im0 Do Q")))))
    sbuf = io.BytesIO()
    scan.save(sbuf)
    scan_data = sbuf.getvalue()

    from belegtool_compress import raster
    from services.render import render_page
    from belegtool_compress.compress import compress_all_methods

    assert raster.get_backend().name == "pdfium"
    png = render_page(data, 0, dpi=100)
    with Image.open(io.BytesIO(png)) as im:
        assert im.size == (827, 1170), im.size
        assert im.convert("RGB").getpixel((20, im.height - 20)) == (255, 0, 0)
    assert render_page(data, 5, dpi=100) == b""
    variants = compress_all_methods(scan_data, dpi=100)
    assert {"jpg", "jpg_color"} <= set(variants), sorted(variants)
    assert all(len(v) < len(scan_data) for v in variants.values())
    print("render_page OK; Kompressionsvarianten:", sorted(variants))
    for name in ("fitz", "pymupdf"):
        assert name not in sys.modules, f"{name} wurde importiert"
    print("OK: Vorschau + Kompression laufen ohne PyMuPDF (pypdfium2 %s)" % __import__("pypdfium2").version.PYPDFIUM_INFO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
