"""Happy-path container extraction coverage (audit C-1, 2026-06-16).

`universal_importer.archives` sat at ~58 % line coverage — the bomb guards and
the plain eml body/attachment were tested, but the TAR extraction loop, the eml
attachment **filename inference** + **inline-image** branches, and the entire
`.msg` path were not. These tests drive those branches with content that converts
headless (PDF / PNG / text / HTML — no Office/COM), and stub `extract_msg.Message`
for the `.msg` path so it runs without Outlook.
"""
import io
import tarfile
from email.message import EmailMessage

import pytest
from PIL import Image

from universal_importer import archives
from helpers import create_valid_pdf


def _png_bytes(color=(30, 120, 200)):
    buf = io.BytesIO()
    Image.new("RGB", (48, 32), color).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- TAR happy path
def test_tar_extracts_each_member_as_pdf():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload in [("a.pdf", create_valid_pdf(pages=1)),
                              ("b.png", _png_bytes())]:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    struct = archives.extract_tar_to_structure(buf.getvalue())
    names = [e["name"] for e in struct]
    assert names == ["a.pdf", "b.png"]
    for e in struct:
        if "content" in e:
            assert e["content"].getvalue().startswith(b"%PDF")


def test_tar_unreadable_member_becomes_folder():
    # A directory member (extractfile -> None) lands as a "nicht importierbar" folder.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        d = tarfile.TarInfo("sub/")
        d.type = tarfile.DIRTYPE
        tf.addfile(d)
        payload = create_valid_pdf(pages=1)
        f = tarfile.TarInfo("sub/a.pdf")
        f.size = len(payload)
        tf.addfile(f, io.BytesIO(payload))
    struct = archives.extract_tar_to_structure(buf.getvalue())
    assert any(e["name"].endswith("a.pdf") for e in struct)


def test_tar_invalid_raises():
    with pytest.raises(ValueError, match="TAR"):
        archives.extract_tar_to_structure(b"not a tar archive at all")


# ----------------------------------------------- EML html body + filename inference
def test_eml_html_body_and_attachment_without_extension():
    msg = EmailMessage()
    msg["Subject"] = "Rechnung 05/2024"
    msg["From"] = "a@b.test"
    msg.set_content("Nur-Text-Fallback")
    msg.add_alternative("<h1>Rechnung</h1><p>Betrag</p>", subtype="html")
    # No extension on the filename → the content-type table must supply ".pdf".
    msg.add_attachment(create_valid_pdf(pages=1),
                       maintype="application", subtype="pdf", filename="beleg")

    struct = archives.extract_email_to_structure(msg.as_bytes())
    names = [e.get("name", "") for e in struct]
    # html body → an .html leaf (subject sanitized: "/" → "-")
    assert any(n.endswith(".html") for n in names)
    # the extensionless attachment was given ".pdf" from its content-type
    assert any(n == "beleg.pdf" for n in names)


def test_eml_inline_image_with_content_id():
    msg = EmailMessage()
    msg["Subject"] = "Mit Bild"
    msg["From"] = "a@b.test"
    msg.set_content("siehe eingebettetes Bild")
    msg.add_related(_png_bytes(), maintype="image", subtype="png", cid="logo1")

    struct = archives.extract_email_to_structure(msg.as_bytes())
    # the inline image is extracted as its own leaf, named from the Content-ID
    assert any("logo1" in e.get("name", "") or e.get("name", "").startswith("Bild_")
               for e in struct)


# --------------------------------------------------------------------- MSG path
class _FakeAtt:
    def __init__(self, long_name, data, short_name=None):
        self.longFilename = long_name
        self.shortFilename = short_name
        self.data = data


class _FakeMsg:
    """Stand-in for extract_msg.Message — no Outlook / OLE file needed."""
    def __init__(self, *, subject="Rechnung", date="2024-05-01", html=None,
                 body=None, rtf=None, attachments=()):
        self.subject = subject
        self.date = date
        self.htmlBody = html
        self.body = body
        self.rtfBody = rtf
        self.attachments = list(attachments)


def _msg_bytes():
    # Must NOT contain b"Content-Type:" / b"From:" so routing picks the .msg branch.
    return b"\xd0\xcf\x11\xe0not-an-eml"


def test_msg_html_body_and_attachment(monkeypatch):
    fake = _FakeMsg(html="<h1>Rechnung</h1>",
                    attachments=[_FakeAtt("beleg.pdf", create_valid_pdf(pages=1))])
    monkeypatch.setattr(archives.extract_msg, "Message", lambda *a, **k: fake)
    struct = archives.extract_email_to_structure(_msg_bytes())
    names = [e.get("name", "") for e in struct]
    assert any(n.endswith(".html") for n in names)
    assert any(n == "beleg.pdf" for n in names)


def test_msg_body_fallback_and_text(monkeypatch):
    # No html → falls through to the plain `body` (.txt).
    fake = _FakeMsg(html=None, body="Rechnungstext", attachments=[])
    monkeypatch.setattr(archives.extract_msg, "Message", lambda *a, **k: fake)
    struct = archives.extract_email_to_structure(_msg_bytes())
    assert any(e.get("name", "").endswith(".txt") for e in struct)


def test_msg_no_body_marks_not_importable(monkeypatch):
    fake = _FakeMsg(html=None, body=None, rtf=None, attachments=[])
    monkeypatch.setattr(archives.extract_msg, "Message", lambda *a, **k: fake)
    struct = archives.extract_email_to_structure(_msg_bytes())
    assert any("nicht importierbar" in e.get("name", "") for e in struct)


def test_msg_attachment_read_error_becomes_folder(monkeypatch):
    class _BadAtt:
        longFilename = "kaputt.pdf"
        shortFilename = None

        @property
        def data(self):
            raise OSError("attachment unreadable")

    fake = _FakeMsg(body="Text", attachments=[_BadAtt()])
    monkeypatch.setattr(archives.extract_msg, "Message", lambda *a, **k: fake)
    struct = archives.extract_email_to_structure(_msg_bytes())
    assert any("nicht importierbar" in e.get("name", "") for e in struct)


def test_msg_parse_failure_raises(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("corrupt OLE")
    monkeypatch.setattr(archives.extract_msg, "Message", _boom)
    with pytest.raises(ValueError, match="MSG"):
        archives.extract_email_to_structure(_msg_bytes())
