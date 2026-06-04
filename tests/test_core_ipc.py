"""End-to-end Step 0a: core server over a real named pipe, multiple clients."""

import uuid

import pytest

from core.client import CoreClient
from core.pipe import default_pipe_name
from core.server import CoreServer
from formats.pdf_node import PDFNode
from formats.pdf_storage import PDFStorage
from helpers import create_valid_pdf


@pytest.fixture
def server():
    # Unique pipe per test so runs never collide with a real core or each other.
    name = default_pipe_name("test-" + uuid.uuid4().hex[:8])
    srv = CoreServer(name)
    srv.start()
    try:
        yield srv, name
    finally:
        srv.stop()


def _make_belegtool(tmp_path) -> str:
    storage = PDFStorage()
    leaf = PDFNode("doc1", pdf_data=create_valid_pdf(pages=1))
    leaf.no_compression = True
    storage.root.add_child(leaf)
    folder = PDFNode("OrdnerA", is_folder=True)
    inner = PDFNode("doc2", pdf_data=create_valid_pdf(pages=1))
    inner.no_compression = True
    folder.add_child(inner)
    storage.root.add_child(folder)
    path = tmp_path / "sample.belegtool"
    storage.save(str(path))
    return str(path)


def test_hello_returns_session(server):
    _srv, name = server
    with CoreClient(name) as c:
        resp = c.hello()
    assert resp["ok"] is True
    assert resp["session"]
    assert "core_version" in resp


def test_open_without_file_gives_empty_document(server):
    _srv, name = server
    with CoreClient(name) as c:
        h = c.hello()
        resp = c.open(path=None, session=h["session"])
    assert resp["ok"] is True
    assert resp["tree"]["name"].startswith("Dokument") and resp["tree"]["children"] == []
    assert resp["can_undo"] is False and resp["can_redo"] is False


def test_open_belegtool_returns_tree(server, tmp_path):
    _srv, name = server
    path = _make_belegtool(tmp_path)
    with CoreClient(name) as c:
        resp = c.open(path=path)
    assert resp["ok"] is True
    tree = resp["tree"]
    assert tree["is_folder"] is True  # name is now the file's basename, not "root"
    assert {child["name"] for child in tree["children"]} == {"doc1", "OrdnerA"}


def test_handles_multiple_simultaneous_connections(server):
    srv, name = server
    c1 = CoreClient(name)
    c2 = CoreClient(name)
    try:
        s1 = c1.hello()["session"]
        s2 = c2.hello()["session"]
        # Both connections are live at once with distinct sessions.
        assert s1 and s2 and s1 != s2
        assert srv.api.session_count() >= 2
        # Each connection still works independently after the other.
        assert c1.open(session=s1)["ok"] is True
        assert c2.open(session=s2)["ok"] is True
    finally:
        c1.close()
        c2.close()


def test_unknown_op_returns_error(server):
    _srv, name = server
    with CoreClient(name) as c:
        resp = c.request({"op": "does-not-exist"})
    assert resp["ok"] is False
    assert "unknown op" in resp["error"]


def test_dispatch_command_updates_document(server):
    _srv, name = server
    with CoreClient(name) as c:
        opened = c.open(path=None)
        sid, root_id = opened["session"], opened["tree"]["id"]
        resp = c.dispatch(
            {"type": "AddFolder", "parent_id": root_id, "name": "Neu",
             "index": None, "new_id": "f1"},
            session=sid)
    assert resp["ok"] is True
    assert [ch["name"] for ch in resp["tree"]["children"]] == ["Neu"]
    assert resp["can_undo"] is True and resp["can_redo"] is False


def test_undo_redo_over_pipe(server):
    _srv, name = server
    with CoreClient(name) as c:
        opened = c.open(path=None)
        sid, root_id = opened["session"], opened["tree"]["id"]
        c.dispatch({"type": "AddFolder", "parent_id": root_id, "name": "Neu",
                    "index": None, "new_id": "f1"}, session=sid)
        undone = c.undo(sid)
        assert undone["tree"]["children"] == [] and undone["can_redo"] is True
        redone = c.redo(sid)
        assert [ch["name"] for ch in redone["tree"]["children"]] == ["Neu"]


def test_dispatch_invalid_command_returns_error(server):
    _srv, name = server
    with CoreClient(name) as c:
        sid = c.open(path=None)["session"]
        resp = c.dispatch({"type": "Rename", "node_id": "missing", "name": "x"}, session=sid)
    assert resp["ok"] is False and "not found" in resp["error"]


def test_dispatch_unknown_session_returns_error(server):
    _srv, name = server
    with CoreClient(name) as c:
        resp = c.dispatch({"type": "Reset", "node_id": "x"}, session="nope")
    assert resp["ok"] is False and "unknown session" in resp["error"]
