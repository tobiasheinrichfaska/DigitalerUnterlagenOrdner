"""Unit tests for the single-writer disk-I/O policy extracted from CoreApi (audit S-1).

`restore_from_bak` and `write_through_lock` are now stateless module functions in
`infra.file_lock`, so they can be exercised directly (cross-platform) with a fake lock —
no Windows handle, no CoreApi, no full save/open round-trip needed.
"""
import os

import pytest

from infra import file_lock


# A valid .belegtool body for the restore heuristic: has a %PDF header AND a %%EOF trailer.
GOOD = b"%PDF-1.7\n" + b"x" * 2000 + b"\n%%EOF\n"
TRUNC = b"%PDF-1.7\n" + b"x" * 50  # header but no trailer → looks like an interrupted save


class _FakeLock:
    """Stand-in for a held FileLock: read_all / overwrite hit the plain file."""
    def __init__(self, path, fail_read=False):
        self.path = path
        self._fail_read = fail_read

    def read_all(self):
        if self._fail_read:
            raise OSError("handle read failed")
        with open(self.path, "rb") as f:
            return f.read()

    def overwrite(self, data):
        with open(self.path, "wb") as f:
            f.write(data)


# ---------------------------------------------------------------- restore_from_bak
def test_restore_noop_without_bak(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(TRUNC)  # truncated, but no .bak → nothing to restore
    file_lock.restore_from_bak(str(p))
    assert p.read_bytes() == TRUNC  # untouched


def test_restore_replaces_truncated_file_from_bak(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(TRUNC)
    (tmp_path / "doc.belegtool.bak").write_bytes(GOOD)
    file_lock.restore_from_bak(str(p))
    assert p.read_bytes() == GOOD                     # restored
    assert not (tmp_path / "doc.belegtool.bak").exists()  # .bak consumed


def test_restore_keeps_complete_file_but_drops_bak(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)  # complete (header + trailer)
    (tmp_path / "doc.belegtool.bak").write_bytes(b"%PDF stale\n%%EOF\n")
    file_lock.restore_from_bak(str(p))
    assert p.read_bytes() == GOOD                     # the good file is kept
    assert not (tmp_path / "doc.belegtool.bak").exists()  # stale .bak removed


# -------------------------------------------------------------- write_through_lock
def test_write_overwrites_and_removes_bak(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(b"OLD CONTENT")
    file_lock.write_through_lock(_FakeLock(str(p)), str(p), b"NEW CONTENT")
    assert p.read_bytes() == b"NEW CONTENT"
    assert not (tmp_path / "doc.belegtool.bak").exists()  # removed after a clean flush


def test_write_aborts_when_prev_unreadable_and_file_nonempty(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(b"IMPORTANT EXISTING")
    with pytest.raises(OSError, match="nicht sichern"):
        file_lock.write_through_lock(_FakeLock(str(p), fail_read=True), str(p), b"NEW")
    assert p.read_bytes() == b"IMPORTANT EXISTING"  # not overwritten — no data loss


def test_write_proceeds_when_prev_unreadable_but_file_empty(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(b"")  # nothing to protect → proceed even if read fails
    file_lock.write_through_lock(_FakeLock(str(p), fail_read=True), str(p), b"NEW")
    assert p.read_bytes() == b"NEW"
