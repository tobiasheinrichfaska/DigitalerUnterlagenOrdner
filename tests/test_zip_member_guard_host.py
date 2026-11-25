"""Host-side half of the zip-member guard tests (the library half lives in
packages/belegtool-archives/tests/test_zip_member_guard.py): the same compression-method
refusal must hold in the variant-blob unpack and the OOXML .rels scan, and a refused
member must show the importer's reason through the injected converter."""
import io
import zipfile

from services import variant_blobs
from universal_importer import archives
from universal_importer.converters import SCAN_UNREADABLE, scan_ooxml_external_targets


def _zip_with_method(members: dict, method: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, payload in members.items():
            z.writestr(zipfile.ZipInfo(name), payload, compress_type=method)
    return buf.getvalue()


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children") or [])


def test_variant_blob_with_bzip2_member_is_discarded_whole():
    blob = _zip_with_method({"150/jpg": b"%PDF-1.4 fake"}, zipfile.ZIP_BZIP2)
    assert variant_blobs.unpack(blob) == {}


def test_rels_scan_fails_closed_on_bzip2_rels(tmp_path):
    rels = (b'<?xml version="1.0"?><Relationships>'
            b'<Relationship TargetMode="External" Type="x/attachedTemplate" '
            b'Target="https://evil.example/t.dotm"/></Relationships>')
    p = tmp_path / "doc.docx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("word/document.xml"), b"<w/>",
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo("word/_rels/document.xml.rels"), rels,
                   compress_type=zipfile.ZIP_BZIP2)
    p.write_bytes(buf.getvalue())
    assert scan_ooxml_external_targets(str(p)) == SCAN_UNREADABLE


def test_zip_member_conversion_failure_shows_its_reason():
    exe = b"MZ" + b"\x00" * 64  # disguised Windows executable named .pdf
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("getarnt.pdf"), exe, compress_type=zipfile.ZIP_DEFLATED)
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(buf.getvalue()))]
    hit = next(n for n in names if n.startswith("getarnt.pdf – nicht importierbar"))
    assert "Windows-Programm" in hit, f"Grund fehlt: {hit!r}"
