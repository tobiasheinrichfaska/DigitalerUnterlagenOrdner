"""Audit finding 4: content-based import validation (magic-byte sniffing)."""

import pytest

from universal_importer import UniversalImporter, _not_importable

verify = UniversalImporter.verify_content_matches_extension


def test_rejects_executable_masquerading_as_pdf():
    with pytest.raises(ValueError, match="EXE|Programm"):
        verify(b"MZ\x90\x00\x03\x00\x00\x00", ".pdf", "rechnung.pdf")


def test_rejects_elf_masquerading_as_png():
    with pytest.raises(ValueError, match="ELF"):
        verify(b"\x7fELF\x02\x01\x01\x00", ".png", "logo.png")


def test_rejects_script_shebang():
    with pytest.raises(ValueError, match="Skript|Shebang"):
        verify(b"#!/bin/sh\nrm -rf /", ".pdf", "evil.pdf")


def test_rejects_extension_content_mismatch():
    # PNG bytes claiming to be a JPEG.
    with pytest.raises(ValueError, match="Unerwarteter Inhalt"):
        verify(b"\x89PNG\r\n\x1a\n", ".jpg", "photo.jpg")


def test_accepts_matching_pdf():
    verify(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3", ".pdf", "ok.pdf")  # no raise


def test_accepts_matching_jpeg():
    verify(b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpg", "ok.jpg")  # no raise


def test_ambiguous_types_are_left_to_converter():
    # Office/zip/text have no leading-magic entry -> not pre-rejected here.
    verify(b"PK\x03\x04whatever", ".docx", "doc.docx")  # no raise
    verify(b"any text content", ".txt", "notes.txt")    # no raise


def test_not_importable_includes_reason():
    node = _not_importable("x.pdf", reason="unerwarteter Typ")
    assert node["children"] == []
    assert "nicht importierbar" in node["name"]
    assert "unerwarteter Typ" in node["name"]
