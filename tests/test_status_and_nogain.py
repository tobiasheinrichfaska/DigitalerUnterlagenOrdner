"""Status model (no-status default, merge/split rules, folder cascade) and the
persisted 'no compression gain' decision that drives the red 'undecided' dot."""

import hashlib

import fitz

from core.api import CoreApi
from core.commands import apply, command_from_dict
from core.engine import RealEngine
from core.model import Document, Node, STATUS_NONE, STATUS_DONE, STATUS_TODO, STATUS_PRIOR_YEAR
from core.session import DocumentSession


def _pdf(n=1):
    doc = fitz.open()
    for i in range(n):
        doc.new_page(width=300, height=300).insert_text((40, 60), f"S{i}" * 30)
    data = doc.tobytes()
    doc.close()
    return data


def _do(doc, cmd, engine=None):
    return apply(doc, command_from_dict(cmd), engine=engine)


# --- default + serialization ------------------------------------------------

def test_new_node_has_no_status():
    assert Node(name="x").status == STATUS_NONE == ""


def test_no_status_roundtrips_through_dict():
    n = Node.from_dict(Node(name="x").to_dict())
    assert n.status == STATUS_NONE


# --- merge rule -------------------------------------------------------------

def _two_leaves(s1, s2):
    a = Node(name="a", id="a", pdf_length=1, original_data=_pdf(), status=s1)
    b = Node(name="b", id="b", pdf_length=1, original_data=_pdf(), status=s2)
    return Document(Node(name="root", id="r", is_folder=True, children=(a, b)))


def test_merge_same_status_kept():
    doc = _two_leaves(STATUS_DONE, STATUS_DONE)
    out = _do(doc, {"type": "Merge", "node_ids": ["a", "b"]}, RealEngine())
    merged = out.root.children[0]
    assert merged.status == STATUS_DONE


def test_merge_different_status_becomes_none():
    doc = _two_leaves(STATUS_DONE, STATUS_PRIOR_YEAR)
    out = _do(doc, {"type": "Merge", "node_ids": ["a", "b"]}, RealEngine())
    assert out.root.children[0].status == STATUS_NONE


def test_merge_with_no_status_participant_becomes_none():
    doc = _two_leaves(STATUS_DONE, STATUS_NONE)
    out = _do(doc, {"type": "Merge", "node_ids": ["a", "b"]}, RealEngine())
    assert out.root.children[0].status == STATUS_NONE


# --- split inherits ---------------------------------------------------------

def test_split_parts_inherit_status():
    leaf = Node(name="doc", id="d", pdf_length=2, original_data=_pdf(2), status=STATUS_PRIOR_YEAR)
    doc = Document(Node(name="root", id="r", is_folder=True, children=(leaf,)))
    out = _do(doc, {"type": "Split", "node_id": "d"}, RealEngine())
    parts = out.root.children
    assert len(parts) == 2
    assert all(p.status == STATUS_PRIOR_YEAR for p in parts)


# --- folder cascade ---------------------------------------------------------

def test_setstatus_on_folder_cascades_to_all_descendants():
    leaf1 = Node(name="l1", id="l1", pdf_length=1, original_data=_pdf())
    leaf2 = Node(name="l2", id="l2", pdf_length=1, original_data=_pdf())
    sub = Node(name="sub", id="sub", is_folder=True, children=(leaf2,))
    folder = Node(name="f", id="f", is_folder=True, children=(leaf1, sub))
    doc = Document(Node(name="root", id="r", is_folder=True, children=(folder,)))
    out = _do(doc, {"type": "SetStatus", "node_id": "f", "status": STATUS_DONE})
    assert out.find("l1").status == STATUS_DONE
    assert out.find("l2").status == STATUS_DONE          # grandchild too
    assert out.find("sub").status == STATUS_NONE         # folders keep no own status


def test_setstatus_leaf_sets_only_that_leaf():
    doc = _two_leaves(STATUS_NONE, STATUS_NONE)
    out = _do(doc, {"type": "SetStatus", "node_id": "a", "status": STATUS_TODO})
    assert out.find("a").status == STATUS_TODO and out.find("b").status == STATUS_NONE


def test_setstatus_many_sets_all_selected():
    doc = _two_leaves(STATUS_NONE, STATUS_NONE)
    out = _do(doc, {"type": "SetStatusMany", "node_ids": ["a", "b"], "status": STATUS_DONE})
    assert out.find("a").status == STATUS_DONE and out.find("b").status == STATUS_DONE


def test_setstatus_many_cascades_folders_and_skips_missing():
    leaf1 = Node(name="l1", id="l1", pdf_length=1, original_data=_pdf())
    leaf2 = Node(name="l2", id="l2", pdf_length=1, original_data=_pdf())
    folder = Node(name="f", id="f", is_folder=True, children=(leaf2,))
    doc = Document(Node(name="root", id="r", is_folder=True, children=(leaf1, folder)))
    out = _do(doc, {"type": "SetStatusMany", "node_ids": ["l1", "f", "gone"], "status": STATUS_PRIOR_YEAR})
    assert out.find("l1").status == STATUS_PRIOR_YEAR
    assert out.find("l2").status == STATUS_PRIOR_YEAR   # folder cascaded
    assert out.find("f").status == STATUS_NONE          # folder keeps no own status


# --- compression-undecided overlay (red dot) -------------------------------

def _tree_flat(tree):
    yield tree
    for c in tree.get("children", []):
        yield from _tree_flat(c)


def _flag(api, sid, node_id):
    resp = api._doc_response_locked(sid)
    return next(n["compression_undecided"] for n in _tree_flat(resp["tree"]) if n["id"] == node_id)


def test_undecided_true_when_not_evaluated(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "undecided.pdf")
    with open(p, "wb") as f:
        f.write(_pdf())
    api.import_paths(sid, [p])
    leaf = next(n for n in api._sessions[sid].document.root.iter() if not n.is_folder)
    assert _flag(api, sid, leaf.id) is True      # never evaluated -> undecided


def test_undecided_false_when_smaller_applied(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    p = str(tmp_path / "applied.pdf")
    with open(p, "wb") as f:
        f.write(_pdf())
    api.import_paths(sid, [p])
    leaf = next(n for n in api._sessions[sid].document.root.iter() if not n.is_folder)
    api._engine.seed_variants(leaf.original_data, {150: {"jpg": _pdf()}})
    api.dispatch(sid, {"type": "Compress", "node_id": leaf.id, "dpi": 150, "method": "jpg"})
    assert _flag(api, sid, leaf.id) is False     # applied ('Lesbarkeit geprüft') -> decided


def test_undecided_false_when_no_gain_persisted():
    n = Node(name="x", id="x", pdf_length=1, original_data=_pdf(), compression_no_gain=True)
    doc = Document(Node(name="root", is_folder=True, children=(n,)))
    api = CoreApi()
    sid = api.open()["session"]
    api._sessions[sid] = DocumentSession(doc, engine=api._engine)
    assert _flag(api, sid, "x") is False          # auto-confirmed no-gain -> decided


# --- no-gain bake + persistence --------------------------------------------

def test_no_gain_is_baked_on_save_and_persists(tmp_path):
    api = CoreApi()
    sid = api.open()["session"]
    import os
    p = str(tmp_path / "src.pdf")
    with open(p, "wb") as f:
        f.write(_pdf())
    api.import_paths(sid, [p])
    leaf = next(n for n in api._sessions[sid].document.root.iter() if not n.is_folder)
    # mark the engine as 'evaluated, nothing smaller' for this source
    api._engine._mcache[(hashlib.sha1(leaf.original_data).digest(), 150)] = {}
    assert _flag(api, sid, leaf.id) is False                  # decided in-session (evaluated, empty)

    bel = str(tmp_path / "out.belegtool")
    assert api.save(sid, bel)["ok"]

    # reopen in a fresh engine (memo empty) -> the persisted flag must keep it decided
    api2 = CoreApi()
    sid2 = api2.open(path=bel)["session"]
    leaf2 = next(n for n in api2._sessions[sid2].document.root.iter() if not n.is_folder)
    assert leaf2.compression_no_gain is True
    assert _flag(api2, sid2, leaf2.id) is False               # not rebuilt, no red dot
