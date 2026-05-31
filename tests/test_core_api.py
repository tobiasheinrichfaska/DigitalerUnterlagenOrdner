"""Unit tests for the in-process core façade (core/api.py) — no pipe, no GUI."""

from core.api import CoreApi
from core.bridge import save_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


def test_hello_creates_session():
    api = CoreApi()
    resp = api.hello()
    assert resp["ok"] and resp["session"] and "core_version" in resp


def test_open_empty_document():
    api = CoreApi()
    resp = api.open()
    assert resp["ok"] is True
    assert resp["tree"]["name"] == "root" and resp["tree"]["children"] == []
    assert resp["can_undo"] is False and resp["can_redo"] is False


def test_open_belegtool(tmp_path):
    src = Document(Node(name="root", is_folder=True, children=(
        Node(name="doc1", pdf_length=1, no_compression=True,
             original_data=create_valid_pdf(pages=1)),
    )))
    path = tmp_path / "s.belegtool"
    save_belegtool(src, path)

    resp = CoreApi().open(path=str(path))
    assert resp["ok"] is True
    assert [c["name"] for c in resp["tree"]["children"]] == ["doc1"]


def test_dispatch_undo_redo():
    api = CoreApi()
    opened = api.open()
    sid, root_id = opened["session"], opened["tree"]["id"]

    after = api.dispatch(sid, {"type": "AddFolder", "parent_id": root_id,
                               "name": "Neu", "index": None, "new_id": "f1"})
    assert [c["name"] for c in after["tree"]["children"]] == ["Neu"]
    assert after["can_undo"] is True

    assert api.undo(sid)["tree"]["children"] == []
    assert [c["name"] for c in api.redo(sid)["tree"]["children"]] == ["Neu"]


def test_dispatch_invalid_command_and_unknown_session():
    api = CoreApi()
    sid = api.open()["session"]
    bad = api.dispatch(sid, {"type": "Rename", "node_id": "missing", "name": "x"})
    assert bad["ok"] is False and "not found" in bad["error"]
    assert api.dispatch("nope", {"type": "Reset", "node_id": "x"})["ok"] is False


def test_independent_sessions():
    api = CoreApi()
    oa = api.open()
    a, a_root = oa["session"], oa["tree"]["id"]
    b = api.open()["session"]
    assert a != b and api.session_count() >= 2

    api.dispatch(a, {"type": "AddFolder", "parent_id": a_root,
                     "name": "X", "index": None, "new_id": "x"})
    # session a changed; session b is independent and still empty
    assert api.undo(b)["tree"]["children"] == []
