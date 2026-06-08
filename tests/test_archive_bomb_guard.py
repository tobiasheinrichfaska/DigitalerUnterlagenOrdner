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
