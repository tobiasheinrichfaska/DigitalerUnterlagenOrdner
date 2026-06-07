"""File lock wired into CoreApi.open/save/release: single-writer, locked in-place save
through the handle (+ .bak guard + restore), and save-as re-lock. Windows-only."""

import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="file lock is Windows-only")

import fitz

from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node


def _pdf(n=1):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=300, height=300).insert_text((40, 60), f"p{i}")
    b = d.tobytes()
    d.close()
    return b


def _make_belegtool(path):
    doc = Document(Node(name="root", id="r", is_folder=True, children=(
        Node(name="A", id="a", pdf_length=1, original_data=_pdf(1)),)))
    save_belegtool(doc, path)


def _locked_api():
    api = CoreApi()
    api._file_lock_enabled = True
    return api


def _names(api, sid):
    return [c["name"] for c in api._doc_response_locked(sid)["tree"]["children"]]


def test_lock_off_by_default(tmp_path):
    p = str(tmp_path / "d.belegtool")
    _make_belegtool(p)
    api = CoreApi()  # default: lock disabled
    sid = api.open(path=p)["session"]
    assert api._locks == {}  # no lock held
    # a second open of the same file succeeds (no lock)
    assert CoreApi().open(path=p)["ok"]


def test_locked_open_blocks_second_open_until_released(tmp_path):
    p = str(tmp_path / "d.belegtool")
    _make_belegtool(p)
    a = _locked_api()
    r1 = a.open(path=p)
    assert r1["ok"]
    b = _locked_api()
    try:
        r2 = b.open(path=p)
        assert r2["ok"] is False and r2.get("code") == "in_use"
        a.release(r1["session"])           # holder releases
        r3 = b.open(path=p)
        assert r3["ok"]                    # now free
        b.release(r3["session"])
    finally:
        a.release(r1["session"])


def test_locked_inplace_save_through_handle_roundtrips(tmp_path):
    p = str(tmp_path / "d.belegtool")
    _make_belegtool(p)
    a = _locked_api()
    sid = a.open(path=p)["session"]
    try:
        leaf = next(n for n in a._sessions[sid].document.root.iter() if not n.is_folder)
        a.dispatch(sid, {"type": "Rename", "node_id": leaf.id, "name": "Umbenannt"})
        res = a.save(sid, p)               # in-place, through the held handle
        assert res["ok"]
        assert not os.path.exists(p + ".bak")  # .bak removed after a successful flush
    finally:
        a.release(sid)
    # reopen fresh → the rename persisted (the locked write produced correct bytes)
    b = _locked_api()
    sid2 = b.open(path=p)["session"]
    try:
        assert "Umbenannt" in _names(b, sid2)
    finally:
        b.release(sid2)


def test_save_as_releases_old_and_locks_new(tmp_path):
    p = str(tmp_path / "d.belegtool")
    p2 = str(tmp_path / "d2.belegtool")
    _make_belegtool(p)
    a = _locked_api()
    sid = a.open(path=p)["session"]
    try:
        assert a.save(sid, p2)["ok"]       # save-as
        other = _locked_api()
        assert other.open(path=p)["ok"]    # old file freed
        r = other.open(path=p2)            # new file is locked by `a`
        assert r["ok"] is False and r.get("code") == "in_use"
        # cleanup the two `other` sessions
        for s in list(other._locks):
            other.release(s)
    finally:
        a.release(sid)


def test_open_restores_from_bak_when_truncated(tmp_path):
    p = str(tmp_path / "d.belegtool")
    _make_belegtool(p)
    with open(p, "rb") as f:
        good = f.read()
    # simulate an interrupted locked save: file truncated, previous bytes left in .bak
    with open(p, "wb") as f:
        f.write(b"")
    with open(p + ".bak", "wb") as f:
        f.write(good)
    a = _locked_api()
    r = a.open(path=p)
    try:
        assert r["ok"]                     # restored from .bak, then opened
        assert not os.path.exists(p + ".bak")  # consumed
        assert "A" in _names(a, r["session"])
    finally:
        a.release(r["session"])
