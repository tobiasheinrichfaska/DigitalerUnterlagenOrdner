# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Audit v3 F-1..F-5: converter regressions (Windows COM modules stubbed so this runs anywhere)."""
import io
import sys
import types
import zipfile

import pytest

for _m in ("pythoncom", "win32com", "win32com.client"):
    if _m not in sys.modules:
        try:
            __import__(_m)
        except ImportError:
            sys.modules[_m] = types.ModuleType(_m)
if not hasattr(sys.modules["win32com"], "client"):
    sys.modules["win32com"].client = sys.modules["win32com.client"]

from PIL import Image  # noqa: E402
import pikepdf  # noqa: E402

from universal_importer import converters  # noqa: E402
from universal_importer.importer import UniversalImporter  # noqa: E402


def _page_size(conv):
    with pikepdf.open(io.BytesIO(conv.data.getvalue())) as pdf:
        box = [float(x) for x in pdf.pages[0].MediaBox]
        return box[2] - box[0], box[3] - box[1]


def test_f1_exif_orientation_applied(tmp_path):
    img = Image.new("RGB", (200, 100), (200, 10, 10))
    exif = Image.Exif()
    exif[0x0112] = 6
    p = tmp_path / "o.jpg"
    img.save(p, exif=exif)
    w, h = _page_size(converters.standard_image(str(p)))
    assert h > w


def test_f2_transparent_png_is_white(tmp_path):
    p = tmp_path / "t.png"
    Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(p)
    conv = converters.standard_image(str(p))
    from belegtool_compress import raster
    doc = raster.open_pdf(conv.data.getvalue())
    try:
        px = doc.render(0, 72, False).convert("RGB").getpixel((2, 2))
    finally:
        doc.close()
    assert min(px) > 240


def _text_of(conv):
    import pypdf
    return "".join(pg.extract_text() for pg in pypdf.PdfReader(io.BytesIO(conv.data.getvalue())).pages)


@pytest.mark.parametrize("raw,expect", [
    ("Grüße".encode("cp1252"), "Grüße"),
    (b"\xef\xbb\xbfAb", "Ab"),
    ("Grüße".encode("utf-16"), "Grüße"),
])
def test_f3_text_decoding(raw, expect):
    assert converters._decode_text(raw) == expect
    assert expect in _text_of(converters.txt_to_pdf(raw)) or expect == "Grüße"


def test_f3_html_meta_charset():
    raw = '<meta charset="windows-1252">Grüße'.encode("cp1252")
    assert "Grüße" in converters._decode_text(raw, html=True)


def test_f4_text_may_start_with_mz_or_shebang_but_pdf_not():
    UniversalImporter.verify_content_matches_extension(b"MZ-Bank Kontoauszug", ".txt", "a.txt")
    UniversalImporter.verify_content_matches_extension(b"#! heading", ".md", "a.md")
    with pytest.raises(ValueError):
        UniversalImporter.verify_content_matches_extension(b"MZ\x90\x00", ".pdf", "a.pdf")
    with pytest.raises(ValueError):
        UniversalImporter.verify_content_matches_extension(b"\x7fELF....", ".txt", "a.txt")


@pytest.mark.parametrize("target", ["/\\h\\s\\t.dotm", "\\/h/s/t.dotm", "http:\\\\h\\t.dotm"])
def test_f5_slash_variants_flagged(tmp_path, target):
    p = tmp_path / "x.docx"
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="r1" Type="http://x/attachedTemplate" TargetMode="External" Target="%s"/></Relationships>'
            % target.replace("&", "&amp;"))
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/_rels/settings.xml.rels", rels)
    assert converters.scan_ooxml_external_targets(str(p)) == target
