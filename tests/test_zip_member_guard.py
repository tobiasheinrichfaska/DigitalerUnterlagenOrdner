"""H3 (audit 2026-11-03): bzip2/LZMA zip members bypass the byte budget.

CPython's zipfile decompresses ZIP_BZIP2/ZIP_LZMA chunks WITHOUT a max_length
(the cap is applied only after the allocation), so ``f.read(remaining + 1)``
bounds the result, not the memory used while inflating. A few-KB member with a
forged small size can allocate GBs. Every place that opens members of an
UNTRUSTED zip must therefore refuse these compression methods up front:
archive import, variant-blob unpack (.belegtool open) and the OOXML .rels scan.
"""
import io
import zipfile

from infra.limits import unsupported_zip_member
from services import variant_blobs
from universal_importer import archives
from universal_importer.converters import SCAN_UNREADABLE, scan_ooxml_external_targets
from helpers import create_valid_pdf


def _zip_with_method(members: dict, method: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, payload in members.items():
            z.writestr(zipfile.ZipInfo(name), payload, compress_type=method)
    return buf.getvalue()


def test_helper_flags_bzip2_and_lzma_allows_stored_and_deflate():
    blob = _zip_with_method({"a": b"x"}, zipfile.ZIP_BZIP2)
    blob2 = _zip_with_method({"a": b"x"}, zipfile.ZIP_LZMA)
    ok = _zip_with_method({"a": b"x"}, zipfile.ZIP_DEFLATED)
    for data, bad in ((blob, True), (blob2, True), (ok, False)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            info = z.infolist()[0]
            assert bool(unsupported_zip_member(info)) is bad


def test_archive_import_refuses_bzip2_member_with_reason():
    blob = _zip_with_method({"doc.pdf": create_valid_pdf(pages=1)}, zipfile.ZIP_BZIP2)
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(blob))]
    assert not any(n == "doc.pdf" for n in names)
    assert any("doc.pdf – nicht importierbar" in n and "Komprimierverfahren" in n
               for n in names)


def test_archive_import_still_takes_deflated_sibling():
    bad = _zip_with_method({"boese.bin": b"x" * 64}, zipfile.ZIP_BZIP2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("gut.pdf"), create_valid_pdf(pages=1),
                   compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(io.BytesIO(bad)) as src:
            info = src.infolist()[0]
            z.writestr(info, src.read("boese.bin"), compress_type=zipfile.ZIP_BZIP2)
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(buf.getvalue()))]
    assert "gut.pdf" in names
    assert any("boese.bin – nicht importierbar" in n for n in names)


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


def _walk(nodes):
    for n in nodes:
        yield n
        yield from _walk(n.get("children") or [])


# --- L10/L11 (audit 2026-11-03): one bad member must not abort the archive, and a
# refused member must SHOW its reason (workspace rule: errors reach the user).

def test_corrupt_member_degrades_instead_of_aborting_the_archive():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("gut.pdf"), create_valid_pdf(pages=1),
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo("kaputt.bin"), b"K" * 512,
                   compress_type=zipfile.ZIP_STORED)
    # Flip a payload byte of kaputt.bin AFTER writing → CRC mismatch on read.
    blob = bytearray(buf.getvalue())
    at = blob.index(b"kaputt.bin") + len("kaputt.bin")
    blob[at + 10] ^= 0xFF
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(bytes(blob)))]
    assert "gut.pdf" in names, "ein defekter Eintrag darf das Archiv nicht abbrechen"
    assert any(n.startswith("kaputt.bin – nicht importierbar (") for n in names)


def test_zip_member_conversion_failure_shows_its_reason():
    exe = b"MZ" + b"\x00" * 64  # disguised Windows executable named .pdf
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("getarnt.pdf"), exe, compress_type=zipfile.ZIP_DEFLATED)
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(buf.getvalue()))]
    hit = next(n for n in names if n.startswith("getarnt.pdf – nicht importierbar"))
    assert "Windows-Programm" in hit, f"Grund fehlt: {hit!r}"


# --- M3 (audit 2026-11-03): tarfile.open on a compressed stream decompresses the
# WHOLE archive while enumerating members — BEFORE the declared-size pre-check.
# The stream inflate must be bounded by the bomb cap.

def test_tgz_stream_inflating_past_the_cap_is_refused(monkeypatch):
    import gzip
    # 160 zero-size members: declared size sum = 0 and member count < cap, so the
    # declared-size pre-checks pass — only a bound on the ACTUAL stream inflation
    # can refuse this before tarfile walks the whole (attacker-sized) stream.
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 64 * 1024)
    inner = _tar_with({f"m{i:03d}.bin": b"" for i in range(160)})  # ~80 KB headers
    assert len(inner) > 64 * 1024
    blob = gzip.compress(inner)
    try:
        archives.extract_tar_to_structure(blob)
        raise AssertionError("übergroßer .tgz-Strom wurde nicht abgelehnt")
    except ValueError as e:
        assert "beim Entpacken" in str(e)


def test_small_tgz_still_imports(monkeypatch):
    import gzip
    blob = gzip.compress(_tar_with({"doc.pdf": create_valid_pdf(pages=1)}))
    names = [n["name"] for n in _walk(archives.extract_tar_to_structure(blob))]
    assert "doc.pdf" in names


def _tar_with(members: dict) -> bytes:
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


# --- Review round 2 (2026-11-04): the overflow charge must not ABORT the import
# for following members, the tar-stream inflation must be charged and bounded by
# the REMAINING budget, double compression must not re-open the original hole,
# and multi-stream gz/bz2 archives must survive.

def _overflow_outer(second_name: str, second_payload: bytes) -> bytes:
    """Outer zip whose NESTED zip passes the declared-size pre-check (checked
    against max_bytes, here 100 KB) but overflows the SHARED budget on the actual
    read, because a filler member spent most of it first. The outer DECLARED sum
    stays small (the nested content is hidden inside the tiny inner-zip member)."""
    filler = b"\x00" * (60 * 1024)
    inner = _zip_with_method({"gross.bin": b"\x00" * (80 * 1024)}, zipfile.ZIP_DEFLATED)
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr(zipfile.ZipInfo("filler.bin"), filler, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo("innen.zip"), inner, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(zipfile.ZipInfo(second_name), second_payload,
                   compress_type=zipfile.ZIP_DEFLATED)
    return outer.getvalue()


def test_members_after_an_overflowed_nested_zip_degrade_instead_of_aborting(monkeypatch):
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 100 * 1024)
    blob = _overflow_outer("danach.txt", b"kleiner Text danach")
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(blob))]
    assert any("innen.zip – nicht importierbar" in n for n in names), names
    assert any(n.startswith("danach.txt – nicht importierbar (Limit überschritten") for n in names), \
        f"Folge-Eintrag bricht den Import ab oder fehlt: {names}"


def test_overflow_charges_the_shared_budget(monkeypatch):
    # Reverting the take_bytes charge must turn this red: after the overflowed
    # nested zip, the budget is spent, so a SECOND nested zip degrades as
    # "Limit überschritten" instead of being decoded all over again.
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 100 * 1024)
    inner = _zip_with_method({"klein.bin": b"\x00" * 1024}, zipfile.ZIP_DEFLATED)
    blob = _overflow_outer("b.zip", inner)
    names = [n["name"] for n in _walk(archives.extract_zip_to_structure(blob))]
    assert any(n.startswith("b.zip – nicht importierbar (Limit überschritten") for n in names), names


def test_tar_stream_inflation_is_charged_and_bounded_by_the_remaining_budget(monkeypatch):
    import gzip
    # Budget largely consumed → the stream limit is the REMAINDER, not max_bytes.
    monkeypatch.setattr(archives, "_ARCHIVE_MAX_UNCOMPRESSED_BYTES", 256 * 1024)
    budget = archives._new_budget()
    budget.take_bytes(236 * 1024)  # 20 KB remain; the inflated tar is ~41 KB
    blob = gzip.compress(_tar_with({f"x{i:02d}.bin": b"" for i in range(80)}))
    try:
        archives.extract_tar_to_structure(blob, _budget=budget)
        raise AssertionError("Strom über dem Restbudget wurde nicht abgelehnt")
    except ValueError as e:
        assert "beim Entpacken" in str(e)
    # And a small stream IS charged: inflating it eats the remainder it used.
    budget2 = archives._new_budget()
    small = gzip.compress(_tar_with({"notiz.txt": b"ein kleiner Text"}))
    archives.extract_tar_to_structure(small, _budget=budget2)
    assert budget2.bytes > 0, "entpackter tar-Strom wurde dem Budget nicht angelastet"


def test_double_compressed_tar_is_refused_not_inflated_unbounded():
    import bz2
    import gzip
    blob = gzip.compress(bz2.compress(_tar_with({"doc.pdf": create_valid_pdf(pages=1)})))
    try:
        names = [n["name"] for n in _walk(archives.extract_tar_to_structure(blob))]
        raise AssertionError(f"gz(bz2(tar)) wurde geöffnet: {names}")
    except ValueError:
        pass  # refused — tarfile must not auto-inflate the second layer unbounded


def test_multi_stream_gzip_tar_keeps_all_members():
    import gzip
    # pbzip2/pigz-style concatenated streams: tarfile's GzipFile handled them; the
    # bounded inflation must too, or members after the first cut silently vanish.
    part1 = _tar_with({"a.pdf": create_valid_pdf(pages=1)})
    # a tar must be read as ONE stream; concatenated gzip MEMBERS carry its halves
    blob = gzip.compress(part1[: len(part1) // 2]) + gzip.compress(part1[len(part1) // 2:])
    names = [n["name"] for n in _walk(archives.extract_tar_to_structure(blob))]
    assert "a.pdf" in names, names


def test_plain_tar_with_bzh_member_name_still_imports():
    blob = _tar_with({"BZh9_bericht.pdf": create_valid_pdf(pages=1)})
    names = [n["name"] for n in _walk(archives.extract_tar_to_structure(blob))]
    assert "BZh9_bericht.pdf" in names, names
