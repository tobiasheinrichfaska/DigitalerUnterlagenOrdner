"""Audit follow-up: archive bomb guards (member count + decompressed-size limits).

Locks the ZIP/TAR protections in `universal_importer.archives` so they can't
silently regress. The constants are monkeypatched low so the tests stay fast and
don't actually materialize hundreds of MB.
"""
import io
import tarfile
import zipfile

import pytest

from universal_importer import archives


def test_zip_rejects_too_many_members(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 3)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(5):
            zf.writestr(f"f{i}.txt", b"x")
    with pytest.raises(ValueError, match="zu viele|Einträge"):
        archives.extract_zip_to_structure(buf.getvalue())


def test_zip_rejects_oversized_declared_total(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 1000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("big.txt", b"A" * 5000)  # declared 5000 > 1000 limit
    with pytest.raises(ValueError, match="unkomprimiert|Limit"):
        archives.extract_zip_to_structure(buf.getvalue())


def test_tar_rejects_too_many_members(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 3)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for i in range(5):
            payload = b"x"
            info = tarfile.TarInfo(f"f{i}.txt")
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="zu viele|Einträge"):
        archives.extract_tar_to_structure(buf.getvalue())


def test_tar_rejects_oversized_declared_total(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 1000)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        payload = b"A" * 5000
        info = tarfile.TarInfo("big.txt")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    with pytest.raises(ValueError, match="unkomprimiert|Limit"):
        archives.extract_tar_to_structure(buf.getvalue())


def _eml_with_attachments(n: int) -> bytes:
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = "Test"
    msg["From"] = "a@b.de"
    msg["To"] = "c@d.de"
    msg.set_content("Body text")
    for i in range(n):
        msg.add_attachment(b"PDFDATA", maintype="application", subtype="octet-stream",
                           filename=f"a{i}.bin")
    return msg.as_bytes()


def test_eml_caps_number_of_parts(monkeypatch):
    # body counts as 1 member; cap at 3 → after body + 2 attachments the rest is bounded.
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 3)
    result = archives.extract_email_to_structure(_eml_with_attachments(10))
    # not all 10 attachments are processed; a "Limit überschritten" marker bounds it.
    assert any("Limit überschritten" in r["name"] for r in result)
    # imported real parts stay well under the 10 attachments + 1 body
    assert len(result) < 11


def test_eml_caps_total_decoded_bytes(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 10)  # tiny
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = "Big"
    msg["From"] = "a@b.de"
    msg.set_content("X" * 5000)  # oversized body alone blows the cap
    result = archives.extract_email_to_structure(msg.as_bytes())
    assert any("nicht importierbar" in r["name"] for r in result)
