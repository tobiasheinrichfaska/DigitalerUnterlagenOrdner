"""Audit follow-up (2026-06-12): archive error-contract + cap notes.

`extract_zip_to_structure` / `extract_tar_to_structure` translate a corrupt container
into a clean ``ValueError`` with a German message — callers (import_paths,
pdf_storage) rely on that contract to surface a friendly error instead of leaking a
``BadZipFile``/``TarError``. These tests lock that translation.

Note on the *actual-read* decompressed-byte cap (`_ArchiveTooLarge`): for a single
flat archive the cheap declared-size pre-check (``sum(file_size)`` / ``sum(size)`` vs
the cap) usually fires first, and a liar entry is rejected by zipfile's CRC check /
clamped by tarfile. Since the shared nested-archive budget (v3.11.4) the running-total
cap IS reachable — nested containers each pass their own pre-check while draining one
common budget — and is exercised in ``test_zip_member_guard.py``. The flat pre-check
is covered in ``test_archive_bomb_guard.py``.
"""
import io
import tarfile
import zipfile

import pytest

from belegtool_archives import archives
from helpers import create_valid_pdf


def test_zip_invalid_bytes_raises_value_error():
    with pytest.raises(ValueError, match="Ungültiges ZIP"):
        archives.extract_zip_to_structure(b"this is not a zip archive")


def test_tar_invalid_bytes_raises_value_error():
    with pytest.raises(ValueError, match="Ungültiges TAR"):
        archives.extract_tar_to_structure(b"this is not a tar archive")


def test_zip_truncated_header_raises_value_error():
    # A valid zip with its central directory chopped off → BadZipFile → ValueError.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", b"hello")
    truncated = buf.getvalue()[:10]
    with pytest.raises(ValueError, match="Ungültiges ZIP"):
        archives.extract_zip_to_structure(truncated)


def test_empty_bytes_is_invalid_for_both():
    with pytest.raises(ValueError, match="Ungültiges ZIP"):
        archives.extract_zip_to_structure(b"")
    with pytest.raises(ValueError, match="Ungültiges TAR"):
        archives.extract_tar_to_structure(b"")


def test_tar_garbage_with_tar_like_size_still_raises():
    # Sanity: random bytes that aren't a real tar must not silently yield an empty list.
    payload = bytes(range(256)) * 4
    assert not tarfile.is_tarfile(io.BytesIO(payload))
    with pytest.raises(ValueError, match="Ungültiges TAR"):
        archives.extract_tar_to_structure(payload)


def test_email_oversized_attachment_refused_not_converted(monkeypatch):
    """L-3: an e-mail attachment that would push the running total over the cap is
    refused ('zu groß') BEFORE conversion — it isn't handed to a converter and can't
    silently exceed the budget. Mirrors the zip/tar early-abort."""
    from email.message import EmailMessage
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 100)
    m = EmailMessage()
    m["From"] = "a@b.de"
    m["Subject"] = "Test"
    m.set_content("hi")  # tiny body, under the cap
    m.add_attachment(b"X" * 300, maintype="application", subtype="octet-stream",
                     filename="big.bin")  # 300 B > the 100 B cap
    result = archives.extract_email_to_structure(m.as_bytes())
    big = [r for r in result if "big.bin" in r["name"]]
    assert big and "zu groß" in big[0]["name"]
    assert "content" not in big[0]  # refused → placeholder folder, not a converted PDF


# --- Audit 2026-11-03: L3 (body bypasses the member cap), L19 (a .msg whose raw
# bytes contain b"From:" was routed to the EML parser), L12 (hidden .msg cause).

def test_mail_body_respects_the_member_cap(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_MEMBERS", 0)
    eml = (b"From: a@example.org\r\nSubject: Voll\r\nContent-Type: text/plain\r\n"
           b"\r\nHallo")
    names = [n["name"] for n in archives.extract_email_to_structure(eml)]
    assert any("Limit überschritten" in n for n in names), names


def test_cfb_msg_with_from_marker_routes_to_the_msg_parser():
    # A real CFB .msg whose HTML body contains an eml-looking marker (<b>From:</b> in an English Outlook
    # reply): the raw bytes hold b"From:", yet it must go to the .msg reader and keep its attachment.
    from msg_fixture import msg
    data = msg("Betreff", None, html="<b>From:</b> someone", attachments=[("anhang.pdf", create_valid_pdf())])
    assert b"From:" in data
    names = [n["name"] for n in archives.extract_email_to_structure(data)]
    assert any(n.startswith("Betreff") for n in names), "CFB-Datei wurde nicht an den MSG-Parser geleitet"
    assert "anhang.pdf" in names


def test_invalid_msg_error_carries_its_cause():
    try:
        archives.extract_email_to_structure(b"\x00\x01\x02 weder eml noch msg")
        raise AssertionError("ungültige MSG wurde nicht abgelehnt")
    except ValueError as e:
        assert e.__cause__ is not None, "Ursache (from e) fehlt"
