# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""R12-1..R12-4: read-only directory / symlink / failure leftovers / retry-safe .bak.

The suite may run as root (directory permissions do not bite), so a read-only DIRECTORY
is simulated: creating any new file inside it and ``os.replace`` into it raise
PermissionError, while the existing target file stays writable."""

import builtins
import io
import os

import pytest

from formats import pdf_storage as P


def _pdf(txt="A"):
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(100, 700, txt)
    c.showPage()
    c.save()
    return b.getvalue()


@pytest.fixture
def ro_dir(monkeypatch):
    state = {"dir": None, "target": None}
    o_open, o_replace = builtins.open, os.replace

    def fake_open(f, mode="r", *a, **k):
        if (state["dir"] and isinstance(f, (str, os.PathLike)) and any(m in mode for m in "wax+")
                and os.path.dirname(os.path.abspath(f)) == state["dir"]
                and os.path.realpath(f) != state["target"]):
            raise PermissionError(13, "Permission denied", str(f))
        return o_open(f, mode, *a, **k)

    def fake_replace(a, b):
        if state["dir"] and os.path.dirname(os.path.abspath(b)) == state["dir"]:
            raise PermissionError(13, "Permission denied", str(b))
        return o_replace(a, b)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(os, "replace", fake_replace)
    return state


def _arm(state, target):
    state["dir"] = os.path.dirname(os.path.realpath(target))
    state["target"] = os.path.realpath(target)


def test_r12_1_write_file_atomic_in_readonly_dir_writes_in_place(tmp_path, ro_dir):
    t = tmp_path / "out.pdf"
    t.write_bytes(b"OLD")
    _arm(ro_dir, t)
    P.write_file_atomic(str(t), b"NEW")
    assert t.read_bytes() == b"NEW"
    assert os.listdir(tmp_path) == ["out.pdf"]


def test_r12_1_export_write_atomic_in_readonly_dir(tmp_path, ro_dir):
    from formats.toc_export import _write_atomic
    t = tmp_path / "out.pdf"
    t.write_bytes(b"OLD")
    _arm(ro_dir, t)
    _write_atomic(str(t), b"NEW")
    assert t.read_bytes() == b"NEW"
    assert os.listdir(tmp_path) == ["out.pdf"]


def test_r12_1_new_file_in_readonly_dir_still_fails(tmp_path, ro_dir):
    t = tmp_path / "new.pdf"
    _arm(ro_dir, t)
    with pytest.raises(PermissionError):
        P.write_file_atomic(str(t), b"NEW")
    assert os.listdir(tmp_path) == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks")
def test_r12_1_symlink_target_is_written_through(tmp_path):
    from formats.toc_export import _write_atomic
    real = tmp_path / "real.pdf"
    real.write_bytes(b"OLD")
    link = tmp_path / "link.pdf"
    os.symlink(real, link)
    _write_atomic(str(link), b"NEW")
    assert os.path.islink(link) and real.read_bytes() == b"NEW"
    P.write_file_atomic(str(link), b"NEWER")
    assert os.path.islink(link) and real.read_bytes() == b"NEWER"


def test_r12_2_unwritable_target_leaves_no_litter_and_no_bak_hint(tmp_path, monkeypatch):
    t = tmp_path / "f.pdf"
    t.write_bytes(b"OLD")
    o_open, o_replace = builtins.open, os.replace

    def fake_open(f, mode="r", *a, **k):
        if os.path.abspath(f) == str(t) and "r+" in mode:
            raise PermissionError(13, "read-only", str(f))
        return o_open(f, mode, *a, **k)

    def fake_replace(a, b):
        raise PermissionError(13, "held open", str(b))

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(os, "replace", fake_replace)
    with pytest.raises(PermissionError) as ei:
        P.write_file_atomic(str(t), b"NEW")
    assert ".bak" not in str(ei.value)
    monkeypatch.undo()
    assert t.read_bytes() == b"OLD"
    assert os.listdir(tmp_path) == ["f.pdf"]


def test_r12_4_commit_files_backup_copy_failure_leaves_no_partial(tmp_path, monkeypatch):
    import shutil
    from formats import toc_export as T
    a, b = tmp_path / "p1.pdf", tmp_path / "p2.pdf"
    a.write_bytes(b"A0")
    b.write_bytes(b"B0")
    staged = [(T._stage_tmp(str(a), b"A1"), str(a)), (T._stage_tmp(str(b), b"B1"), str(b))]
    real = shutil.copyfile
    n = {"c": 0}

    def bad_copy(s, d, *args, **k):
        n["c"] += 1
        if n["c"] == 2:
            open(d, "wb").write(b"xx")  # partial
            raise OSError(28, "No space left")
        return real(s, d, *args, **k)

    monkeypatch.setattr(shutil, "copyfile", bad_copy)
    with pytest.raises(OSError):
        T._commit_files(staged)
    monkeypatch.undo()
    assert a.read_bytes() == b"A0" and b.read_bytes() == b"B0"
    assert sorted(os.listdir(tmp_path)) == ["p1.pdf", "p2.pdf"]


def _inplace_fault(monkeypatch, target, fail_writes, fail_restore_opens=()):
    """os.replace refused; the n-th r+b open of target (1-based) in fail_writes writes
    half the data then fails; opens listed in fail_restore_opens fail outright."""
    o_open = builtins.open
    st = {"n": 0}

    class W:
        def __init__(w, h):
            w.h = h

        def __getattr__(w, x):
            return getattr(w.h, x)

        def __enter__(w):
            return w

        def __exit__(w, *e):
            w.h.close()

        def write(w, b):
            w.h.write(b"X" * 50)
            w.h.flush()
            raise OSError(5, "I/O error")

    def fake_open(f, mode="r", *a, **k):
        if isinstance(f, str) and os.path.abspath(f) == target and mode == "r+b":
            st["n"] += 1
            if st["n"] in fail_restore_opens:
                raise OSError(5, "share unreachable")
            h = o_open(f, mode, *a, **k)
            return W(h) if st["n"] in fail_writes else h
        return o_open(f, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(13, "held", b)))
    return st


def test_r12_3_retry_never_overwrites_good_bak_with_corrupt_target(tmp_path, monkeypatch):
    good = _pdf("GOOD")
    new = _pdf("NEW" * 50)
    t = tmp_path / "doc.belegtool"
    t.write_bytes(good)
    # save 1: write (open #1) fails midway AND the restore (open #2) fails
    _inplace_fault(monkeypatch, str(t), fail_writes={1}, fail_restore_opens={2})
    with pytest.raises(OSError):
        P.write_file_atomic(str(t), new)
    monkeypatch.undo()
    bak = str(t) + ".bak"
    assert open(bak, "rb").read() == good and t.read_bytes() != good
    # save 2 (retry): the pre-flight restore (open #1) fails -> must refuse, bak intact
    _inplace_fault(monkeypatch, str(t), fail_writes=set(), fail_restore_opens={1})
    with pytest.raises(OSError):
        P.write_file_atomic(str(t), new)
    monkeypatch.undo()
    assert open(bak, "rb").read() == good
    # save 3: restore works, write fails again, restore works -> target back to GOOD
    _inplace_fault(monkeypatch, str(t), fail_writes={2}, fail_restore_opens=())
    with pytest.raises(OSError):
        P.write_file_atomic(str(t), new)
    monkeypatch.undo()
    assert t.read_bytes() == good


def test_r12_3_retry_write_fails_again_and_restore_fails_keeps_good_bak(tmp_path, monkeypatch):
    good = _pdf("GOOD")
    new = _pdf("NEW" * 50)
    t = tmp_path / "doc.belegtool"
    t.write_bytes(good)
    _inplace_fault(monkeypatch, str(t), fail_writes={1}, fail_restore_opens={2})
    with pytest.raises(OSError):
        P.write_file_atomic(str(t), new)
    monkeypatch.undo()
    # retry: pre-flight restore ok (#1), write fails (#2), restore fails (#3)
    _inplace_fault(monkeypatch, str(t), fail_writes={2}, fail_restore_opens={3})
    with pytest.raises(OSError):
        P.write_file_atomic(str(t), new)
    monkeypatch.undo()
    assert open(str(t) + ".bak", "rb").read() == good
