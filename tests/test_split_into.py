"""SplitInto: chunks of N pages, optionally into a new folder named after the node."""

import fitz
import pytest

from core.model import Document, Node
from core.commands import Split, SplitInto, Rotate, Merge, apply, CommandError
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


# --- committed node (compressed, source dropped on save → original_data None) ----
# Regression: splitting such a node previously failed with "node has no data to split".

def _committed_doc(pages=4):
    """A committed leaf: only the compressed current_data exists, no source."""
    leaf = Node(name="doc", is_folder=False, original_data=None,
                current_data=make_pdf(pages), pdf_length=pages,
                is_compressed=True, compression_method="jpg")
    return Document(Node(name="root", is_folder=True, children=(leaf,))), leaf.id


def test_split_committed_node_per_page():
    doc, nid = _committed_doc(3)
    d = apply(doc, Split(node_id=nid), engine=ENGINE)
    kids = d.root.children
    assert len(kids) == 3
    for k in kids:
        assert not k.is_folder and k.pdf_length == 1
        assert k.original_data is None and k.current_data  # stays committed (no source)
        assert k.is_compressed is True


def test_split_into_committed_node_chunks():
    doc, nid = _committed_doc(5)
    d = apply(doc, SplitInto(node_id=nid, size=2), engine=ENGINE)
    kids = d.root.children
    assert [k.pdf_length for k in kids] == [2, 2, 1]
    assert all(k.original_data is None and k.is_compressed for k in kids)


def test_rotate_committed_node_stays_committed():
    doc, nid = _committed_doc(2)
    before = doc.root.children[0].current_data
    d = apply(doc, Rotate(node_id=nid, direction="right"), engine=ENGINE)
    n = d.root.children[0]
    assert n.original_data is None and n.is_compressed is True   # still committed
    assert n.current_data and n.current_data != before          # bytes rotated in place


def _committed_leaf(pages, dpi):
    return Node(name=f"d{pages}", is_folder=False, original_data=None,
                current_data=make_pdf(pages), pdf_length=pages,
                is_compressed=True, compression_method="jpg", dpi_current=dpi)


def test_merge_committed_nodes_keeps_all_pages_same_dpi():
    a, b = _committed_leaf(2, 100), _committed_leaf(3, 100)
    doc = Document(Node(name="root", is_folder=True, children=(a, b)))
    d = apply(doc, Merge(node_ids=[a.id, b.id]), engine=ENGINE)
    m = d.root.children[0]
    assert ENGINE.page_count(m.current_data) == 5
    # stays committed — no resurrected source (else re-compress/reset would re-open)
    assert m.original_data is None and m.is_compressed is True


def test_merge_committed_nodes_keeps_all_pages_differing_dpi():
    # Differing DPI: before any fix, committed pages were lost; the first fix then
    # resurrected a fake source. Now it stays committed and keeps every page.
    a, b = _committed_leaf(2, 100), _committed_leaf(3, 200)
    doc = Document(Node(name="root", is_folder=True, children=(a, b)))
    d = apply(doc, Merge(node_ids=[a.id, b.id]), engine=ENGINE)
    m = d.root.children[0]
    assert ENGINE.page_count(m.current_data) == 5
    assert m.original_data is None and m.is_compressed is True
