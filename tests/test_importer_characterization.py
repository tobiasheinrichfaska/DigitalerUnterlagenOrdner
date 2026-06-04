"""Characterization tests for the headless importer paths, to lock behaviour
before `universal_importer` is split into an `importers/` subpackage (structure
audit finding 2). Each converter must keep producing a valid %PDF / structure.

The Office (COM) path needs Word/Excel/PowerPoint installed and is intentionally
not covered here — it cannot run headless/deterministically.
"""

import io
import zipfile
from email.message import EmailMessage

import pytest
from PIL import Image

from universal_importer import (
    UniversalImporter,
    extract_zip_to_structure,
    extract_email_to_structure,
)
from helpers import create_valid_pdf


def _png_bytes(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def test_pdf_passthrough_is_valid():
    out = UniversalImporter.convert(create_valid_pdf(pages=2), name="x.pdf")
    assert out.data.getvalue().startswith(b"%PDF")


def test_png_converts_to_pdf():
    out = UniversalImporter.convert(_png_bytes(), name="pic.png")
    assert out.data.getvalue().startswith(b"%PDF")


def test_txt_converts_to_pdf():
    out = UniversalImporter.convert(b"Hallo Welt\nZeile 2", name="notes.txt")
    assert out.data.getvalue().startswith(b"%PDF")


def test_html_converts_to_pdf_and_ignores_local_img():
    # the file:// image must not break conversion nor be fetched (LFI guard) —
    # we still get a valid PDF out.
    html = b"<h1>Titel</h1><p>Text</p><img src='file:///C:/secret.pdf'>"
    out = UniversalImporter.convert(html, name="page.html")
    assert out.data.getvalue().startswith(b"%PDF")


def test_zip_extracts_each_member_as_pdf():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", create_valid_pdf(pages=1))
        z.writestr("b.png", _png_bytes())
    struct = extract_zip_to_structure(buf.getvalue())
    names = [e["name"] for e in struct]
    assert names == ["a.pdf", "b.png"]
    for e in struct:
        # importable members carry PDF bytes; non-importable become folders
        if "content" in e:
            assert e["content"].getvalue().startswith(b"%PDF")


def test_eml_extracts_body_and_attachment():
    msg = EmailMessage()
    msg["Subject"] = "Rechnung"
    msg["From"] = "a@b.test"
    msg["To"] = "c@d.test"
    msg.set_content("Bitte Anhang prüfen.")
    msg.add_attachment(create_valid_pdf(pages=1),
                       maintype="application", subtype="pdf", filename="beleg.pdf")

    struct = extract_email_to_structure(msg.as_bytes())
    # at least the body + the attachment leaf
    assert len(struct) >= 2
    flat = " ".join(e.get("name", "") for e in struct)
    assert "beleg.pdf" in flat
