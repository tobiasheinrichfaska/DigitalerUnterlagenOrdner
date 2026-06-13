"""Audit follow-up (2026-06-12): archive error-contract + cap notes.

`extract_zip_to_structure` / `extract_tar_to_structure` translate a corrupt container
into a clean ``ValueError`` with a German message — callers (import_paths,
pdf_storage) rely on that contract to surface a friendly error instead of leaking a
``BadZipFile``/``TarError``. These tests lock that translation.

Note on the *actual-read* decompressed-byte cap (`_ArchiveTooLarge`): it is
unreachable through CPython's zipfile/tarfile by construction. The cheap declared-size
pre-check (``sum(file_size)`` / ``sum(size)`` vs the cap) rejects any archive whose
*declared* total exceeds the cap, and an entry that *reads* larger than declared is a
liar entry that zipfile rejects with a CRC error (and tarfile clamps to the header
size) before our running-total check can fire. The pre-check + the stdlib's own
integrity validation dominate; the running-total cap is belt-and-suspenders. The
reachable pre-check is covered in ``test_archive_bomb_guard.py``.
"""
import io
import tarfile
import zipfile

import pytest

from universal_importer import archives


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
