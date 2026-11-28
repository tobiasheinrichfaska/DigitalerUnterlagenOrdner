# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Regression tests for the 2026-11 core audit (C-1/A-1, C-2, C-3, C-6, C-7, C-8, C-9)."""

import io
import threading
from pathlib import Path

import pytest

from core.commands import (AddFolder, CommandError, InsertNodes, Merge, MoveMany, SetDatev,
                           apply, Delete)
from core.model import Document, Node
from core.render_policy import predict_window
from core.session import DocumentSession


def _doc():
    a = Node(name="a", id="a", original_data=b"X" * 20, current_data=b"X" * 20, pdf_length=1)
    b = Node(name="b", id="b", original_data=b"Y" * 20, current_data=b"Y" * 20, pdf_length=1)
    f = Node(name="f", id="f", is_folder=True)
    return Document(Node(name="root", id="root", is_folder=True, children=(a, b, f)))


def _ids(doc):
    return [n.id for n in doc.root.iter()]


def test_insert_nodes_reids_colliding_subtree():
    d = _doc()
    imp = Node(name="imp", id="f", is_folder=True,
               children=(Node(name="c", id="a", original_data=b"Z" * 20),))
    d2 = apply(d, InsertNodes("root", (imp,)))
    ids = _ids(d2)
    assert len(ids) == len(set(ids)) == 6
    new_leaf = d2.root.children[-1].children[0]
    assert new_leaf.id != "a" and new_leaf.original_data == b"Z" * 20
    # deleting the imported copy leaves the original
    d3 = apply(d2, Delete(d2.root.children[-1].id))
    assert d3.find("a").original_data == b"X" * 20


def test_insert_nodes_keeps_noncolliding_ids():
    d = _doc()
    imp = Node(name="n", id="fresh", is_folder=True)
    d2 = apply(d, InsertNodes("root", (imp,)))
    assert d2.find("fresh") is not None


def test_insert_nodes_dupes_within_batch():
    d = _doc()
    n1 = Node(name="n1", id="q"); n2 = Node(name="n2", id="q")
    d2 = apply(d, InsertNodes("root", (n1, n2)))
    ids = _ids(d2)
    assert len(ids) == len(set(ids))


def test_move_many_duplicate_ids_moves_once():
    d2 = apply(_doc(), MoveMany(("a", "a"), "f"))
    assert [c.id for c in d2.find("f").children] == ["a"]


class _E:
    def merge(self, parts):
        return b"".join(parts)

    def page_count(self, b):
        return 1


def test_merge_duplicate_ids_rejected():
    with pytest.raises(CommandError):
        apply(_doc(), Merge(("a", "a")), _E())


def test_silent_datev_survives_undo_and_redo():
    s = DocumentSession(_doc())
    s.dispatch(AddFolder("root", "x"))
    s.apply_silent(SetDatev({"doc_guid": "g"}))
    s.undo()
    assert s.document.root.datev == {"doc_guid": "g"}
    s.redo()
    assert s.document.root.datev == {"doc_guid": "g"}
    s.undo()
    assert not s.dirty


def test_rotate_keeps_acroform():
    import pikepdf
    from core.engine import RealEngine
    src = Path(__file__).resolve().parent.parent / "webui" / "public" / "spike-form.pdf"
    data = src.read_bytes()
    out = RealEngine().rotate(data, 90)
    with pikepdf.open(io.BytesIO(data)) as a, pikepdf.open(io.BytesIO(out)) as b:
        assert "/AcroForm" in a.Root
        assert "/AcroForm" in b.Root
        assert len(b.Root.AcroForm.Fields) == len(a.Root.AcroForm.Fields)


def test_all_methods_single_flight(monkeypatch):
    import formats.compress_pdf_bytes as cpb
    from core.engine import RealEngine
    calls = []
    gate = threading.Event()

    def fake(pdf, dpi=150, cancel=None, **kw):
        calls.append(1)
        gate.wait(2)
        return {"jpg": b"s"}
    monkeypatch.setattr(cpb, "compress_all_methods", fake)
    e = RealEngine()
    data = b"%PDF-fake-bytes"
    res = []
    ts = [threading.Thread(target=lambda: res.append(e.compress_methods(data, 150))) for _ in range(2)]
    for t in ts:
        t.start()
    import time; time.sleep(0.2)
    gate.set()
    for t in ts:
        t.join(5)
    assert len(calls) == 1 and res == [{"jpg": 1}, {"jpg": 1}]


def test_repeated_focus_keeps_backward_bias():
    assert predict_window([20, 19, 19], 40) == predict_window([20, 19], 40)
