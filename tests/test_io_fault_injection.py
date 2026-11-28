# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Failure-injection regressions for user-data I/O (audit y4, IO-1/2/5/7/8).

A tiny injector makes ``os.replace`` refuse (target held open elsewhere) and fails the
N-th write to a matching file half way (ENOSPC); each test iterates N until the
operation completes without the fault firing. Invariant: a failed write never leaves
the user's previous file truncated, and a failed save never claims success."""

import base64
import builtins
import errno
import glob
import hashlib
import io
import os

import pikepdf
import pytest

from core.api import CoreApi


def _pdf(n=2, txt="A"):
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    for i in range(n):
        c.drawString(100, 700, f"{txt} page {i}" + "x" * 200)
        c.showPage()
    c.save()
    return b.getvalue()


def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class Faults:
    """refuse_replace: os.replace raises PermissionError (sticky). fail_write: the N-th
    write to a file whose path contains ``match`` writes half the data, then ENOSPC."""

    def __init__(self, match, n=None, refuse_replace=False, replace_n=None):
        self.match, self.n, self.refuse = match, n, refuse_replace
        self.replace_n, self.wc, self.rc, self.fired = replace_n, 0, 0, False
        self.wfired = False  # a WRITE fault fired (a mere refused replace is not a failure)

    def __enter__(self):
        self.o_open, self.o_replace = builtins.open, os.replace
        me = self

        class W:
            def __init__(w, f, path):
                w.f, w.path = f, str(path)

            def write(w, b):
                if me.n is not None and me.match in w.path:
                    me.wc += 1
                    if me.wc == me.n:
                        me.fired = me.wfired = True
                        w.f.write(b[:max(1, len(b) // 2)])
                        w.f.flush()
                        raise OSError(errno.ENOSPC, "No space left on device")
                return w.f.write(b)

            def __getattr__(w, k):
                return getattr(w.f, k)

            def __enter__(w):
                w.f.__enter__()
                return w

            def __exit__(w, *a):
                return w.f.__exit__(*a)

        def fopen(file, mode="r", *a, **k):
            f = me.o_open(file, mode, *a, **k)
            if isinstance(file, (str, os.PathLike)) and any(c in mode for c in "wax+"):
                return W(f, file)
            return f

        def freplace(src, dst, *a, **k):
            if me.match in str(dst) and (me.refuse or me.replace_n is not None):
                me.rc += 1
                if me.refuse or me.rc == me.replace_n:
                    me.fired = True
                    raise PermissionError(errno.EACCES, "held open")
            return me.o_replace(src, dst, *a, **k)

        builtins.open, os.replace = fopen, freplace
        return self

    def __exit__(self, *a):
        builtins.open, os.replace = self.o_open, self.o_replace


def _api_with_doc(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    src = tmp_path / "in.pdf"
    src.write_bytes(_pdf(3))
    assert api.import_paths(sid, [str(src)])["ok"]
    return api, sid


def _dirty_edit(api, sid, name):
    nid = api._sessions[sid].document.root.children[0].id
    assert api.dispatch(sid, {"type": "Rename", "node_id": nid, "name": name})["ok"]


def _leftovers(d, keep):
    return [f for f in os.listdir(d) if f not in keep]


@pytest.mark.parametrize("refuse", [True, False])
def test_io1_save_never_destroys_original(tmp_path, refuse):
    api, sid = _api_with_doc(tmp_path)
    tgt = str(tmp_path / "out.belegtool")
    assert api.save(sid, tgt)["ok"]
    good = _sha(tgt)
    for n in range(1, 12):
        _dirty_edit(api, sid, f"e{n}")
        with Faults("out.belegtool", n=n, refuse_replace=refuse) as fi:
            res = api.save(sid, tgt)
        if not fi.wfired:
            assert res["ok"]
            break
        if res["ok"]:
            with pikepdf.open(tgt):
                pass
            good = _sha(tgt)
        else:
            assert _sha(tgt) == good, f"original damaged at fault {n}"
            assert api._sessions[sid].dirty
            assert not _leftovers(tmp_path, {"in.pdf", "out.belegtool"}), os.listdir(tmp_path)
    else:
        pytest.fail("fault never stopped firing")


def test_io2_embed_failure_never_reports_ok_with_corrupt_file(tmp_path):
    api, sid = _api_with_doc(tmp_path)
    nid = api._sessions[sid].document.root.children[0].id
    src = api._sessions[sid].document.find(nid).original_data
    api._engine.seed_variants(src, {150: {"jpg": b"V" * 5000, "pikepdf": b"W" * 5000}})
    tgt = str(tmp_path / "out.belegtool")
    assert api.save(sid, tgt)["ok"]
    for n in range(1, 14):
        _dirty_edit(api, sid, f"e{n}")
        # the embed swap is the SECOND replace of a save; refuse every replace
        with Faults("out.belegtool", n=n, refuse_replace=True) as fi:
            res = api.save(sid, tgt)
        with pikepdf.open(tgt) as p:  # whatever happened, the file must stay a valid PDF
            assert len(p.pages) > 0
        if not fi.wfired:
            assert res["ok"]
            break
        if not res["ok"]:
            assert api._sessions[sid].dirty
        assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f], os.listdir(tmp_path)
    else:
        pytest.fail("fault never stopped firing")


def test_io2_embed_atomic_swap_failure_is_reported_not_swallowed(tmp_path):
    """Direct unit: when neither swap nor in-place write can land, embed_variants
    raises (save → ok:false) and the base file is byte-identical."""
    from core.bridge import document_to_storage
    from services.variant_store import embed_variants
    api, sid = _api_with_doc(tmp_path)
    doc = api._sessions[sid].document
    nid = doc.root.children[0].id
    api._engine.seed_variants(doc.find(nid).original_data, {150: {"jpg": b"V" * 5000}})
    tgt = str(tmp_path / "base.belegtool")
    document_to_storage(doc).save(tgt)
    good = _sha(tgt)
    with Faults("base.belegtool", n=2, refuse_replace=True) as fi:
        with pytest.raises(OSError):
            embed_variants(tgt, doc, api._engine)
    assert fi.fired
    assert _sha(tgt) == good
    assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f]


@pytest.mark.parametrize("refuse", [True, False])
def test_io5_local_pdf_write_is_atomic(tmp_path, refuse):
    p = str(tmp_path / "user.pdf")
    orig = _pdf(3, "ORIG")
    with open(p, "wb") as f:
        f.write(orig)
    api = CoreApi()
    sid = api.open(None, p)["session"]
    for n in range(1, 8):
        edited = _pdf(3, f"EDIT{n}")
        with Faults("user.pdf", n=n, refuse_replace=refuse) as fi:
            r = api.save_pdf_bytes(sid, base64.b64encode(edited).decode())
        cur = open(p, "rb").read()
        if not fi.wfired:
            assert r["local_saved"] == p and cur == edited
            break
        assert r["local_saved"] is None and r["local_error"]
        assert cur == orig, f"local pdf damaged at fault {n}"
        assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f]
    else:
        pytest.fail("fault never stopped firing")


def test_io7_keyboardinterrupt_in_embed_swap_leaves_no_tmp(tmp_path):
    api, sid = _api_with_doc(tmp_path)
    nid = api._sessions[sid].document.root.children[0].id
    api._engine.seed_variants(api._sessions[sid].document.find(nid).original_data,
                              {150: {"jpg": b"V" * 5000}})
    tgt = str(tmp_path / "out.belegtool")
    assert api.save(sid, tgt)["ok"]
    _dirty_edit(api, sid, "x")
    real, calls = os.replace, []

    def ki_replace(a, b, *x, **k):
        calls.append(b)
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return real(a, b, *x, **k)
    os.replace = ki_replace
    try:
        with pytest.raises(KeyboardInterrupt):
            api.save(sid, tgt)
    finally:
        os.replace = real
    assert not [f for f in os.listdir(tmp_path) if ".tmp-" in f]


def test_io7_keyboardinterrupt_in_materialize_leaks_no_view_dir(tmp_path, monkeypatch):
    import tempfile
    import core.bridge as bridge
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    api, sid = _api_with_doc(tmp_path)
    ids = [n.id for n in api._sessions[sid].document.root.iter()]

    def boom(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(bridge, "save_belegtool", boom)
    with pytest.raises(KeyboardInterrupt):
        api.materialize_subset(sid, ids, "tag")
    assert not glob.glob(str(tmp_path / "beleg_view_*"))


def test_io7_keyboardinterrupt_in_open_releases_file_lock(tmp_path, monkeypatch):
    import core.api as ca
    from infra import file_lock
    p = tmp_path / "a.belegtool"
    api, sid = _api_with_doc(tmp_path)
    assert api.save(sid, str(p))["ok"]

    class FakeLock:
        path = str(p)
        released = 0

        def release(self):
            FakeLock.released += 1
    monkeypatch.setattr(api, "_should_lock", lambda path: True)
    monkeypatch.setattr(file_lock, "acquire_lock", lambda path: FakeLock())

    def boom(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(ca, "load_belegtool", boom)
    with pytest.raises(KeyboardInterrupt):
        api.open(None, str(p))
    assert FakeLock.released == 1


@pytest.mark.parametrize("bad", [None, "", 0, 12, b"x", ["a"]])
def test_io8_save_rejects_missing_path(tmp_path, monkeypatch, bad):
    monkeypatch.chdir(tmp_path)
    api, sid = _api_with_doc(tmp_path)
    before = set(os.listdir(tmp_path))
    r = api.save(sid, bad)
    assert r["ok"] is False and r.get("error")
    assert set(os.listdir(tmp_path)) == before
