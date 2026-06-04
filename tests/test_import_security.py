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


# --- HTML/email link policy (xhtml2pdf link_callback) ---------------------
block = UniversalImporter._block_remote_link


@pytest.mark.parametrize("uri", [
    "http://evil.example/pixel.png",         # remote → tracking/SSRF
    "https://evil.example/x.png",
    "//evil.example/x.png",                  # protocol-relative
    "file:///C:/Windows/win.ini",            # local file → LFI
    "file:///etc/passwd",
    "C:\\Users\\me\\secret.pdf",             # absolute local path
    "/etc/shadow",                           # absolute posix path
    "../../secret.pdf",                       # relative path traversal
    "secret.pdf",                             # bare relative
    "ftp://host/x",                           # other scheme
])
def test_html_link_blocks_remote_and_local(uri):
    # Only self-contained inline content may load; everything else is dropped,
    # so a malicious HTML/.eml/.msg cannot embed a local file or call out.
    assert block(uri, "") is None


@pytest.mark.parametrize("uri", [
    "data:image/png;base64,iVBORw0KGgo=",    # inline base64 image
    "DATA:image/png;base64,iVBORw0KGgo=",    # case-insensitive
    "cid:logo@mail",                          # MIME content-id (no FS/network)
    "  data:image/gif;base64,R0lGOD  ",      # surrounding whitespace tolerated
])
def test_html_link_allows_inline_only(uri):
    assert block(uri, "") == uri
