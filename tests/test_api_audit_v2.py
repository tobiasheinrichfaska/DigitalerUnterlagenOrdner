# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Regression tests for the v2 api audit (A-2 … A-9): node-lock coverage, stale no-gain
verdicts, global-lock stalls, session reuse, lock path compare, pdftool binding
cleanup, save_node_back ordering, IPC error reply + session cleanup."""

import base64
import os
import threading

import pytest
import types

from core.api import CoreApi
from core.commands import SetNodeBytes
from core.model import Document, Node
from core.session import DocumentSession
from helpers import create_valid_pdf


def _api(doc):
    api = CoreApi()
    sid = api.open()["session"]
    api._sessions[sid] = DocumentSession(doc, engine=api._engine)
    return api, sid


def _tree():
    leaf = Node(name="scan", id="L", pdf_length=1, original_data=create_valid_pdf(pages=1))
    folder = Node(name="F", id="F", is_folder=True, children=(leaf,))
    return Document(Node(name="root", id="r", is_folder=True, children=(folder,)))


# --- A-2 -------------------------------------------------------------------
def test_a2_deleting_ancestor_folder_of_locked_node_is_blocked():
    api, sid = _api(_tree())
    assert api.open_node_in_pdftool(sid, "L")["ok"]
    r = api.dispatch(sid, {"type": "Delete", "node_id": "F"})
    assert not r["ok"] and r["code"] == "node_locked"


def test_a2_undo_redo_refused_while_a_node_is_locked():
    api, sid = _api(_tree())
    assert api.dispatch(sid, {"type": "Rename", "node_id": "L", "name": "x"})["ok"]
    assert api.open_node_in_pdftool(sid, "L")["ok"]
    for op in (api.undo, api.redo):
        r = op(sid)
        assert not r["ok"] and r["code"] == "node_locked"


# --- A-3 -------------------------------------------------------------------
def test_a3_stale_no_gain_verdict_is_dropped_when_bytes_changed_mid_evaluation():
    api, sid = _api(_tree())
    new_bytes = create_valid_pdf(pages=2)

    class Eng:
        def compress_methods(self, data, dpi, cancel=None):
            api._sessions[sid].dispatch(SetNodeBytes("L", new_bytes))  # bytes replaced mid-call
            return {}
    api._engine = Eng()
    api.compress_options(sid, "L", 150)
    node = api._sessions[sid].document.find("L")
    assert node.original_data == new_bytes
    assert node.compression_no_gain is False


# --- A-4 -------------------------------------------------------------------
def test_a4_slow_dispatch_does_not_stall_other_sessions():
    api, sid = _api(_tree())
    entered, release = threading.Event(), threading.Event()
    s = api._sessions[sid]
    real = s.dispatch

    def slow(cmd):
        entered.set()
        release.wait(5)
        return real(cmd)
    s.dispatch = slow
    t = threading.Thread(target=lambda: api.dispatch(sid, {"type": "Rename", "node_id": "L", "name": "y"}))
    t.start()
    try:
        assert entered.wait(5)
        done = []
        probe = threading.Thread(target=lambda: done.append(api.session_count()))
        probe.start()
        probe.join(2)
        assert done, "another caller was blocked by the in-flight mutation (global lock held)"
    finally:
        release.set()
        t.join(5)
    assert api._sessions[sid].document.find("L").name == "y"


# --- A-5 -------------------------------------------------------------------
def test_a5_reopening_in_same_session_drops_old_datev_baseline(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    api._datev_baseline[sid] = {"opened_sha256": "abc"}
    api.open(session=sid)
    assert sid not in api._datev_baseline


# --- A-6 -------------------------------------------------------------------
def test_a6_save_with_equivalent_path_spelling_goes_through_the_lock(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "a.belegtool")
    api._paths[sid] = p
    api._locks[sid] = types.SimpleNamespace(path=p, release=lambda: None)
    calls = []
    api._save_through_lock = lambda lock, path, doc, alt: calls.append(path)
    variant = str(tmp_path / "sub" / ".." / "a.belegtool")
    assert api.save(sid, variant)["ok"]
    assert calls, "in-place save under lock must use the locked write path"


def test_a6_degraded_session_save_as_onto_locked_original_goes_through_lock(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "a.belegtool")
    api._paths[sid] = None  # degraded: unbound
    api._locks[sid] = types.SimpleNamespace(path=p, release=lambda: None)
    calls = []
    api._save_through_lock = lambda lock, path, doc, alt: calls.append(path)
    assert api.save(sid, p)["ok"]
    assert calls


# --- A-7 -------------------------------------------------------------------
def test_a7_close_session_cleans_pdftool_bindings_and_tool_sessions():
    api, sid = _api(_tree())
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    api.close_session(sid)
    assert not api._node_locks and not api._pdftool_bindings
    assert pt not in api._sessions


# --- A-8 -------------------------------------------------------------------
def test_a8_save_node_back_with_missing_target_leaves_tool_bytes_unchanged():
    api, sid = _api(_tree())
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    before = base64.b64decode(api.get_pdf_bytes(pt)["data_b64"])
    # target vanishes from the owner (bypassing the lock guard)
    api._sessions[sid].dispatch(__import__("core.commands", fromlist=["Delete"]).Delete("L"))
    edited = create_valid_pdf(pages=3)
    r = api.save_node_back(pt, base64.b64encode(edited).decode())
    assert not r["ok"]
    assert base64.b64decode(api.get_pdf_bytes(pt)["data_b64"]) == before


# --- A-9 -------------------------------------------------------------------
def test_a9_server_dispatch_returns_error_reply_and_cleans_up(monkeypatch):
    import importlib
    import sys
    import types as _t
    for name in ("win32file", "pywintypes", "win32pipe", "win32event", "win32security", "win32con",
                 "winerror", "win32api"):
        try:
            importlib.import_module(name)
        except Exception:
            monkeypatch.setitem(sys.modules, name, _t.ModuleType(name))
    if not hasattr(sys.modules["pywintypes"], "error"):
        monkeypatch.setattr(sys.modules["pywintypes"], "error", Exception, raising=False)
    monkeypatch.delitem(sys.modules, "core.ipc.server", raising=False)
    monkeypatch.delitem(sys.modules, "core.ipc.pipe", raising=False)
    try:
        from core.ipc.server import CoreServer
    except Exception:
        import pytest
        pytest.skip("pipe transport not importable here")
    srv = CoreServer("x")
    base = srv.api.session_count()

    def boom(*a, **k):
        raise RuntimeError("kaputt")
    srv.api.open = boom
    r = srv._safe_dispatch({"op": "open"}, set())
    assert r["ok"] is False and "kaputt" in r["error"]

    owned = set()
    r = srv._safe_dispatch({"op": "hello"}, owned)
    assert r["ok"] and owned == {r["session"]}
    srv._cleanup_sessions(owned)
    assert srv.api.session_count() == base


# --- T-4: PDF-Tool save payload validation ---------------------------------
@pytest.mark.parametrize("payload", ["!!!!", "a", "", base64.b64encode(b"garbage").decode()])
def test_t4_save_node_back_rejects_bad_payload_and_changes_nothing(payload):
    api, sid = _api(_tree())
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    owner_before = api._sessions[sid].document.find("L").original_data
    tool_before = base64.b64decode(api.get_pdf_bytes(pt)["data_b64"])
    r = api.save_node_back(pt, payload)
    assert r["ok"] is False and r["error"]
    assert api._sessions[sid].document.find("L").original_data == owner_before
    assert base64.b64decode(api.get_pdf_bytes(pt)["data_b64"]) == tool_before


def test_t4_save_node_back_valid_payload_updates_bytes_and_pdf_length():
    api, sid = _api(_tree())
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    edited = create_valid_pdf(pages=3)
    assert api.save_node_back(pt, base64.b64encode(edited).decode())["ok"]
    n = api._sessions[sid].document.find("L")
    assert n.original_data == edited and n.pdf_length == 3


def test_t4_save_pdf_bytes_rejects_garbage_without_disk_write(tmp_path):
    pdf = tmp_path / "x.pdf"
    good = create_valid_pdf(pages=1)
    pdf.write_bytes(good)
    api = CoreApi()
    sid = api.open(path=str(pdf))["session"]
    for payload in (base64.b64encode(b"garbage").decode(), "!!!!"):
        assert api.save_pdf_bytes(sid, payload)["ok"] is False
        assert api.update_pdf_bytes(sid, payload)["ok"] is False
    assert pdf.read_bytes() == good
