# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Mutation-testing blind spots in core/ (commands, model, session) — see audit x3 (MU-1..MU-8)."""

import pytest

from core import commands
from core.commands import AddFolder, Merge, SetDatev, SplitInto, apply, Rename
from core.engine import RealEngine
from core.model import Document, Node, remove_nodes
from core.session import DocumentSession

ENGINE = RealEngine()


def _pdf(pages):
    import fitz
    d = fitz.open()
    for _ in range(pages):
        d.new_page(width=200, height=200)
    b = d.tobytes()
    d.close()
    return b


def _small_doc():
    a = Node(name="a", id="a", original_data=b"DATA-LONG-ENOUGH")
    return Document(Node(name="root", id="root", is_folder=True, children=(a,)))


# MU-1  core/commands.py:851  `f"{node.name}_{i + 1}"` (committed SplitInto branch)
def test_split_into_committed_part_names_are_one_based_and_ordered():
    leaf = Node(name="doc", original_data=None, current_data=_pdf(5), pdf_length=5,
                is_compressed=True, compression_method="jpg")
    doc = Document(Node(name="root", is_folder=True, children=(leaf,)))
    d = apply(doc, SplitInto(node_id=leaf.id, size=2), engine=ENGINE)
    assert [k.name for k in d.root.children] == ["doc_1", "doc_2", "doc_3"]
    d2 = apply(doc, SplitInto(node_id=leaf.id, size=2, into_folder=True), engine=ENGINE)
    assert [k.name for k in d2.root.children[0].children] == ["doc_1", "doc_2", "doc_3"]


# MU-2  core/commands.py:253  Merge.__post_init__ `if not isinstance(..., tuple)`
def test_merge_normalises_list_node_ids_to_hashable_tuple():
    m = Merge(["a", "b"])
    assert m.node_ids == ("a", "b") and isinstance(m.node_ids, tuple)
    assert hash(m) == hash(Merge(("a", "b")))
    assert m == Merge(("a", "b"))


# MU-3  core/commands.py:281  `_handler` decorator must hand the function back
def test_handler_decorator_returns_the_function():
    class _Marker:
        pass

    def fn():
        return 1

    try:
        assert commands._handler(_Marker)(fn) is fn
        assert commands._HANDLERS[_Marker] is fn
    finally:
        commands._HANDLERS.pop(_Marker, None)
    # the real handlers stay callable at module level (nobody may rely on them being None)
    assert callable(commands._split_into) and callable(commands._merge)


# MU-4  core/model.py:126  Node.from_dict default for a missing `is_compressed`
def test_from_dict_missing_flags_default_false():
    n = Node.from_dict({"name": "x"})
    assert n.is_compressed is False
    assert n.no_compression is False and n.compression_no_gain is False
    assert n.collapsed is False and n.is_folder is False


# MU-5  core/model.py:312  remove_nodes(root in ids) must raise, like remove_node
def test_remove_nodes_refuses_the_root():
    root = Node(name="root", id="root", is_folder=True,
                children=(Node(name="a", id="a"),))
    with pytest.raises(ValueError):
        remove_nodes(root, ["a", "root"])
    with pytest.raises(ValueError):
        Document(root).remove_nodes(["root"])


# MU-6  core/session.py:120,129  undo()/redo() return the resulting document
def test_undo_and_redo_return_the_current_document():
    s = DocumentSession(_small_doc())
    start = s.document
    s.dispatch(Rename("a", "A!"))
    edited = s.document
    assert s.undo() is s.document and s.document is start
    assert s.redo() is s.document and s.document is edited
    # the no-op branches return the unchanged document too
    assert s.redo() is edited
    s.undo()
    assert s.undo() is start


# MU-7  core/session.py:104  a silent SetDatev must also be carried into the REDO stack
def test_silent_datev_is_carried_into_redo_snapshots():
    s = DocumentSession(_small_doc())
    s.dispatch(AddFolder("root", "x"))
    s.undo()                                   # the edit now sits on the redo stack
    s.apply_silent(SetDatev({"doc_guid": "g"}))
    assert s.document.root.datev == {"doc_guid": "g"}
    s.redo()
    assert s.document.root.datev == {"doc_guid": "g"}
    assert [c.name for c in s.document.root.children][-1] == "x"  # the folder came back too


# MU-8  core/model.py:86  Node.__post_init__ scrubs lone surrogates from name AND tags
def test_node_scrubs_lone_surrogates_in_name_and_tags():
    n = Node(name="a\ud83db", tags=("t\ud800x", "ok"))
    assert n.name == "a�b"
    assert n.tags == ("t�x", "ok")
    n.name.encode("utf-8")           # would raise before the scrub existed
    for t in n.tags:
        t.encode("utf-8")
    assert Node(name="plain", tags=("x",)).tags == ("x",)
