"""PDF-Tool node binding: lock a node while it's edited in the PDF-Tool, block
content changes from the organizer (allow reposition/rename), save edited bytes back
into the node, and break/close the binding. See docs/pdf-tool.md."""

import base64

import fitz

from core.api import CoreApi
from core.commands import SetNodeBytes
from core.model import Document, Node
from core.session import DocumentSession


def _pdf(tag="A"):
    doc = fitz.open()
    doc.new_page(width=200, height=200).insert_text((20, 20), f"pdf-{tag}")
    data = doc.tobytes()
    doc.close()
    return data


def _api_with_leaf():
    leaf = Node(name="scan", id="L", pdf_length=1, original_data=_pdf("A"))
    doc = Document(Node(name="root", id="r", is_folder=True, children=(leaf,)))
    api = CoreApi()
    sid = api.open()["session"]
    api._sessions[sid] = DocumentSession(doc, engine=api._engine)
    return api, sid


def test_open_node_locks_and_serves_bytes():
    api, sid = _api_with_leaf()
    res = api.open_node_in_pdftool(sid, "L")
    assert res["ok"]
    assert api.node_locked(sid, "L")
    b = api.get_pdf_bytes(res["session"])
    assert b["ok"] and base64.b64decode(b["data_b64"]).startswith(b"%PDF")


def test_double_open_is_rejected():
    api, sid = _api_with_leaf()
    api.open_node_in_pdftool(sid, "L")
    res2 = api.open_node_in_pdftool(sid, "L")
    assert not res2["ok"] and res2["code"] == "node_locked"


def test_folder_cannot_be_opened():
    folder = Node(name="f", id="F", is_folder=True, children=())
    doc = Document(Node(name="root", id="r", is_folder=True, children=(folder,)))
    api = CoreApi()
    sid = api.open()["session"]
    api._sessions[sid] = DocumentSession(doc, engine=api._engine)
    assert not api.open_node_in_pdftool(sid, "F")["ok"]


def test_content_change_on_locked_node_is_blocked():
    api, sid = _api_with_leaf()
    api.open_node_in_pdftool(sid, "L")
    r = api.dispatch(sid, {"type": "Rotate", "node_id": "L", "direction": "right"})
    assert not r["ok"] and r["code"] == "node_locked" and r["node_id"] == "L"


def test_reposition_and_rename_allowed_on_locked_node():
    api, sid = _api_with_leaf()
    api.dispatch(sid, {"type": "AddFolder", "parent_id": "r", "name": "F", "new_id": "F"})
    api.open_node_in_pdftool(sid, "L")
    assert api.dispatch(sid, {"type": "Move", "node_id": "L", "new_parent_id": "F"})["ok"]
    assert api.dispatch(sid, {"type": "Rename", "node_id": "L", "name": "neu"})["ok"]
    assert api.dispatch(sid, {"type": "SetStatus", "node_id": "L", "status": "erfasst"})["ok"]


def test_save_node_back_writes_bytes_and_dirties_owner():
    api, sid = _api_with_leaf()
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    # simulate an edit in the pdf-tool session (e.g. a filled form)
    edited = _pdf("EDITED")
    pt_leaf = next(n for n in api._sessions[pt].document.root.iter() if not n.is_folder)
    api._sessions[pt].dispatch(SetNodeBytes(pt_leaf.id, edited))

    res = api.save_node_back(pt)
    assert res["ok"]
    owner_leaf = api._sessions[sid].document.find("L")
    assert owner_leaf.original_data == edited        # new bytes landed in the node
    assert owner_leaf.is_compressed is False         # compression reset (new source)
    assert api._sessions[sid].dirty                  # organizer marked unsaved


def test_save_node_back_accepts_edited_bytes_from_pdfjs():
    # PDF.js saveDocument() output arrives as base64 over the bridge; save_node_back
    # writes exactly those bytes (no need to pre-dispatch into the tool session).
    api, sid = _api_with_leaf()
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    edited = _pdf("FREETEXT")
    res = api.save_node_back(pt, base64.b64encode(edited).decode())
    assert res["ok"]
    assert api._sessions[sid].document.find("L").original_data == edited
    assert api._sessions[sid].dirty


def test_self_authored_text_survives_save_and_reopen():
    # The cross-session promise: text the user adds in the PDF-Tool (a FreeText
    # annotation, as PDF.js saveDocument() writes it) is still there — and still a
    # FreeText object, i.e. re-editable — when the node is reopened in a later session.
    api, sid = _api_with_leaf()
    pt = api.open_node_in_pdftool(sid, "L")["session"]

    served = base64.b64decode(api.get_pdf_bytes(pt)["data_b64"])
    doc = fitz.open(stream=served, filetype="pdf")
    doc[0].add_freetext_annot(fitz.Rect(20, 60, 180, 90), "Meine Notiz")
    edited = doc.tobytes()
    doc.close()

    assert api.save_node_back(pt, base64.b64encode(edited).decode())["ok"]
    api.close_pdftool(pt)

    pt2 = api.open_node_in_pdftool(sid, "L")["session"]   # reopen the SAME node, fresh session
    reopened = base64.b64decode(api.get_pdf_bytes(pt2)["data_b64"])
    doc2 = fitz.open(stream=reopened, filetype="pdf")
    kinds = [a.type[1] for a in doc2[0].annots()]
    doc2.close()
    assert "FreeText" in kinds   # the self-authored text persisted and is still an editable object


def test_break_binding_unblocks_the_organizer_op():
    api, sid = _api_with_leaf()
    api.open_node_in_pdftool(sid, "L")
    assert not api.dispatch(sid, {"type": "Rotate", "node_id": "L", "direction": "right"})["ok"]
    api.break_node_binding(sid, "L")
    assert not api.node_locked(sid, "L")
    assert api.dispatch(sid, {"type": "Rotate", "node_id": "L", "direction": "right"})["ok"]


def test_close_pdftool_releases_lock_and_frees_session():
    api, sid = _api_with_leaf()
    pt = api.open_node_in_pdftool(sid, "L")["session"]
    api.close_pdftool(pt)
    assert not api.node_locked(sid, "L")
    assert pt not in api._sessions
