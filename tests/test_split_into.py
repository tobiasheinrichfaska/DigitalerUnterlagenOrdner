"""SplitInto: chunks of N pages, optionally into a new folder named after the node."""

import fitz
import pytest

from core.model import Document, Node
from core.commands import SplitInto, apply, CommandError
from core.engine import RealEngine

ENGINE = RealEngine()


def make_pdf(pages):
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=200, height=200)
    b = doc.tobytes()
    doc.close()
    return b


def _doc(pages=4):
    leaf = Node(name="doc", is_folder=False, original_data=make_pdf(pages), pdf_length=pages)
    return Document(Node(name="root", is_folder=True, children=(leaf,))), leaf.id


def test_per_page_in_place():
    doc, nid = _doc(4)
    d = apply(doc, SplitInto(node_id=nid, size=1, into_folder=False), engine=ENGINE)
    kids = d.root.children
    assert len(kids) == 4 and all(not k.is_folder and k.pdf_length == 1 for k in kids)
    assert [k.name for k in kids] == ["doc_1", "doc_2", "doc_3", "doc_4"]


def test_chunks_in_place():
    doc, nid = _doc(5)
    d = apply(doc, SplitInto(node_id=nid, size=2), engine=ENGINE)
    assert [k.pdf_length for k in d.root.children] == [2, 2, 1]  # 5 → 2,2,1


def test_into_folder_per_page():
    doc, nid = _doc(3)
    d = apply(doc, SplitInto(node_id=nid, size=1, into_folder=True), engine=ENGINE)
    assert len(d.root.children) == 1
    folder = d.root.children[0]
    assert folder.is_folder and folder.name == "doc"
    assert len(folder.children) == 3 and all(c.pdf_length == 1 for c in folder.children)


def test_into_folder_chunks():
    doc, nid = _doc(5)
    d = apply(doc, SplitInto(node_id=nid, size=2, into_folder=True), engine=ENGINE)
    folder = d.root.children[0]
    assert folder.is_folder and folder.name == "doc"
    assert [c.pdf_length for c in folder.children] == [2, 2, 1]


def test_in_place_single_chunk_is_noop():
    doc, nid = _doc(3)
    d = apply(doc, SplitInto(node_id=nid, size=10, into_folder=False), engine=ENGINE)
    assert d.root.children[0].id == nid  # one chunk would == original → unchanged


def test_no_data_rejected():
    doc = Document(Node(name="root", is_folder=True, children=(Node(name="x", is_folder=False),)))
    nid = doc.root.children[0].id
    with pytest.raises(CommandError):
        apply(doc, SplitInto(node_id=nid, size=1), engine=ENGINE)
