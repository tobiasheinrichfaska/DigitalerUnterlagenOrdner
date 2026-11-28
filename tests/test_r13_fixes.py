# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""R13-1..R13-3 regressions: /Parent cycle in rotate, _safe_filename joiners, stale swap marker."""
import errno
import io
import os
import threading

import pikepdf
import pytest

from core.api import CoreApi
from core.engine import RealEngine
from formats import pdf_storage as ps


def _run_bounded(fn, secs=10):
    out = {}

    def w():
        try:
            out["r"] = fn()
        except BaseException as e:  # noqa: BLE001
            out["e"] = e
    t = threading.Thread(target=w, daemon=True)
    t.start()
    t.join(secs)
    assert not t.is_alive(), "call hung (cycle not guarded)"
    return out


def _cyc(kind):
    p = pikepdf.new()
    p.add_blank_page(page_size=(200, 300))
    if kind == "root":
        p.Root.Pages.Parent = p.Root.Pages
    else:  # intermediate node pointing at itself
        mid = p.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Pages, Kids=p.Root.Pages.Kids,
                                                 Count=1, Parent=p.Root.Pages))
        mid.Parent = mid
        p.Root.Pages.Kids = pikepdf.Array([mid])
        p.pages[0].obj.Parent = mid
    b = io.BytesIO()
    p.save(b)
    return b.getvalue()


@pytest.mark.parametrize("kind", ["root", "mid"])
def test_r13_1_rotate_survives_parent_cycle(kind):
    data = _cyc(kind)
    out = _run_bounded(lambda: RealEngine().rotate(data, 90))
    assert "e" not in out, out.get("e")
    with pikepdf.open(io.BytesIO(out["r"])) as q:
        assert int(q.pages[0].obj["/Rotate"]) == 90


def test_r13_1_rotate_inherited_rotate_unchanged():
    p = pikepdf.new()
    p.add_blank_page(page_size=(200, 300))
    p.Root.Pages["/Rotate"] = 90
    b = io.BytesIO()
    p.save(b)
    out = RealEngine().rotate(b.getvalue(), 90)
    with pikepdf.open(io.BytesIO(out)) as q:
        assert int(q.pages[0].obj["/Rotate"]) == 180


def test_r13_2_joiners_and_marks_kept():
    f = CoreApi._safe_filename
    for n in ("👨‍👩‍👧 Familie", "می‌خواهم", "שלום‏ עולם", "a‎b"):
        assert f(n, "X") == n
    for bad, good in (("a​b", "ab"), ("a‮b", "ab"), ("a⁧b", "ab"),
                      ("a﻿b", "ab"), ("a\x85b", "ab"), ("a\x01b", "ab")):
        assert f(bad, "X") == good


def test_r13_2_inner_spaces_before_dot_kept():
    f = CoreApi._safe_filename
    assert f("Beleg 1 .5", "X") == "Beleg 1 .5"
    assert f("Q1 . Q2", "X") == "Q1 . Q2"
    assert f("Rechnung. ", "X") == "Rechnung"
    assert f("a . ", "X") == "a"
    assert f("NUL", "X") == "X"


def test_r13_3_stale_marker_cleared_by_atomic_save(tmp_path, monkeypatch):
    T = str(tmp_path / "a.belegtool")
    open(T, "wb").write(b"v1")
    ps._make_guard(T)
    open(T, "wb").write(b"v1-hybr")  # crash mid in-place write
    tmp = T + ".tmp-1"
    open(tmp, "wb").write(b"v2-NEW")
    ps.swap_file_in(tmp, T)
    assert sorted(os.listdir(tmp_path)) == ["a.belegtool"]
    # later: replace refused + in-place write fails -> must restore v2, not stale v1
    real_fsync = os.fsync
    n = {"n": 0}

    def deny(a, b):
        raise PermissionError(errno.EACCES, "held")

    def fs(fd):
        n["n"] += 1
        if n["n"] >= 2:
            raise OSError(errno.ENOSPC, "disk full")
        return real_fsync(fd)
    monkeypatch.setattr(os, "replace", deny)
    monkeypatch.setattr(os, "fsync", fs)
    tmp = T + ".tmp-1"
    open(tmp, "wb").write(b"v3-NEW")
    with pytest.raises(OSError):
        ps.swap_file_in(tmp, T)
    monkeypatch.undo()
    assert open(T, "rb").read() == b"v2-NEW"


def test_r13_3_user_bak_without_marker_untouched(tmp_path):
    T = str(tmp_path / "a.belegtool")
    open(T, "wb").write(b"v1")
    open(T + ".bak", "wb").write(b"user")
    tmp = T + ".tmp-1"
    open(tmp, "wb").write(b"v2")
    ps.swap_file_in(tmp, T)
    assert open(T + ".bak", "rb").read() == b"user"
