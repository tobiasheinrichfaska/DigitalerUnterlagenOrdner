# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
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


# --- N-2 + Nebenbefund 1 (QS 2026-11-04): incomplete locked writes ------------------

class _FailingLock(_FakeLock):
    """overwrite() raises after writing only a prefix — an interrupted locked save."""
    def overwrite(self, data):
        with open(self.path, "wb") as f:
            f.write(data[:10])
        raise OSError("Unvollständig geschrieben: 10 von %d Bytes" % len(data))


def test_failed_locked_save_keeps_bak_and_wip(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)
    with pytest.raises(OSError):
        file_lock.write_through_lock(_FailingLock(str(p)), str(p), b"NEW " * 100)
    assert (tmp_path / "doc.belegtool.bak").read_bytes() == GOOD  # safety copy kept
    assert (tmp_path / "doc.belegtool.wip").exists()              # marker kept


def test_restore_prefers_bak_when_wip_marker_present(tmp_path):
    """After an interrupted locked save the on-disk file can still carry BOTH markers
    (%PDF head from the new write, %%EOF tail from the old bytes), so the head/tail
    heuristic alone would keep it. The .wip marker forces the restore."""
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)  # passes the head/tail check
    (tmp_path / "doc.belegtool.bak").write_bytes(b"%PDF previous good\n%%EOF\n")
    (tmp_path / "doc.belegtool.wip").write_bytes(b"wip")
    file_lock.restore_from_bak(str(p))
    assert p.read_bytes() == b"%PDF previous good\n%%EOF\n"       # restored
    assert not (tmp_path / "doc.belegtool.bak").exists()
    assert not (tmp_path / "doc.belegtool.wip").exists()


def test_retry_save_after_failure_keeps_the_good_bak(tmp_path):
    """Second save attempt while .wip is still present: the .bak (last good bytes)
    must NOT be refreshed from the current on-disk state. If the retry fails too,
    the good .bak must still be there."""
    p = tmp_path / "doc.belegtool"
    p.write_bytes(TRUNC)  # current on-disk state after the first failed save
    (tmp_path / "doc.belegtool.bak").write_bytes(GOOD)
    (tmp_path / "doc.belegtool.wip").write_bytes(b"wip")
    with pytest.raises(OSError):
        file_lock.write_through_lock(_FailingLock(str(p)), str(p), b"NEW " * 100)
    assert (tmp_path / "doc.belegtool.bak").read_bytes() == GOOD  # untouched


def test_retry_save_success_clears_bak_and_wip(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(TRUNC)
    (tmp_path / "doc.belegtool.bak").write_bytes(GOOD)
    (tmp_path / "doc.belegtool.wip").write_bytes(b"wip")
    file_lock.write_through_lock(_FakeLock(str(p)), str(p), b"NEW CONTENT")
    assert p.read_bytes() == b"NEW CONTENT"
    assert not (tmp_path / "doc.belegtool.bak").exists()
    assert not (tmp_path / "doc.belegtool.wip").exists()


def test_restore_drops_stale_wip_without_bak(tmp_path):
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)
    (tmp_path / "doc.belegtool.wip").write_bytes(b"wip")  # no .bak to restore from
    file_lock.restore_from_bak(str(p))
    assert p.read_bytes() == GOOD                          # untouched
    assert not (tmp_path / "doc.belegtool.wip").exists()   # stale marker cleaned


class _SneakyRemoveLock(_FakeLock):
    """overwrite() succeeds, but a concurrent reader's restore_from_bak raced us and
    already deleted the .wip marker (and the .bak) mid-save."""
    def overwrite(self, data):
        super().overwrite(data)
        for suffix in (".wip", ".bak"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass


def test_successful_save_survives_a_raced_wip_removal(tmp_path):
    """QS-Bewertung 2026-11-04: os.remove(wip) was unguarded — a second process's
    restore_from_bak during the write made a COMPLETED save report FileNotFoundError."""
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)
    file_lock.write_through_lock(_SneakyRemoveLock(str(p)), str(p), b"NEW CONTENT")
    assert p.read_bytes() == b"NEW CONTENT"  # the save is complete and reported ok


def test_real_overwrite_short_write_raises(tmp_path):
    """Exercise the REAL FileLock.overwrite (not a fake): a WriteFile that returns
    n<=0 must raise before SetEndOfFile — the fix itself, not a paraphrase."""
    win32file = pytest.importorskip("win32file")
    p = tmp_path / "doc.belegtool"
    p.write_bytes(GOOD)
    lock = file_lock.FileLock(str(p)).acquire()
    try:
        calls = {"n": 0}
        real_write = win32file.WriteFile

        def short_write(handle, data):
            calls["n"] += 1
            if calls["n"] == 1:
                real_write(handle, data[:10])
                return (0, 10)  # partial progress
            return (0, 0)  # then the stall the old code swallowed via `break`

        import unittest.mock as mock
        with mock.patch.object(win32file, "WriteFile", side_effect=short_write):
            with pytest.raises(OSError, match="Unvollständig"):
                lock.overwrite(b"X" * 100)
    finally:
        lock.release()
