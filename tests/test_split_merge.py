"""Unit tests for Split / Merge engine commands (D3b)."""

import pytest

from core.model import Document, Node
from core.commands import (
    CommandError,
    Merge,
    Split,
    apply,
    command_from_dict,
    command_to_dict,
)


class FakeEngine:
    """Pages are '|'-separated tokens — split/merge/page_count stay consistent."""

    def page_count(self, b: bytes) -> int:
        return (b.count(b"|") + 1) if b else 0

    def split(self, b: bytes):
        return list(b.split(b"|"))

    def merge(self, parts):
        return b"|".join(parts)

    def compress(self, b, dpi, method=None):
        return None

    def rotate(self, b, angle):
        return b


ENGINE = FakeEngine()


# --- Split -----------------------------------------------------------------

def split_doc() -> Document:
    a = Node(name="a", id="a", pdf_length=3, original_data=b"P1|P2|P3")
    z = Node(name="z", id="z", pdf_length=1, original_data=b"Z")
    return Document(Node(name="root", id="root", is_folder=True, children=(a, z)))


def test_split_replaces_leaf_with_page_leaves_in_place():
    d0 = split_doc()
    d1 = apply(d0, Split("a"), ENGINE)
    kids = d1.root.children
    assert [k.name for k in kids] == ["a_1", "a_2", "a_3", "z"]
    parts = [k.original_data for k in kids[:3]]
    assert parts == [b"P1", b"P2", b"P3"]
    assert all(k.pdf_length == 1 and k.no_compression for k in kids[:3])
    assert d0.find("a") is not None  # original untouched (pure)


def test_split_single_page_is_noop():
    d0 = Document(Node(name="root", id="root", is_folder=True,
                       children=(Node(name="a", id="a", original_data=b"ONLYONE"),)))
    assert apply(d0, Split("a"), ENGINE) is d0


def test_split_errors():
    with pytest.raises(CommandError):
        apply(split_doc(), Split("root"), ENGINE)        # folder, not leaf
    with pytest.raises(CommandError):
        apply(split_doc(), Split("missing"), ENGINE)
    with pytest.raises(CommandError):
        apply(split_doc(), Split("a"))                   # no engine


# --- Merge -----------------------------------------------------------------

def merge_doc(a_kw=None, b_kw=None) -> Document:
    a = Node(name="a", id="a", pdf_length=1, original_data=b"A", **(a_kw or {}))
    b = Node(name="b", id="b", pdf_length=1, original_data=b"B", **(b_kw or {}))
    z = Node(name="z", id="z", pdf_length=1, original_data=b"Z")
    return Document(Node(name="root", id="root", is_folder=True, children=(a, b, z)))


def test_merge_uncompressed_concatenates():
    d1 = apply(merge_doc(), Merge(("a", "b")), ENGINE)
    kids = d1.root.children
    assert [k.id for k in kids][1:] == ["z"]  # merged sits first, z after
    merged = kids[0]
    assert merged.name == "a" and merged.original_data == b"A|B"
    assert merged.pdf_length == 2
    assert merged.is_compressed is False and merged.current_data is None


def test_merge_keeps_position_among_remaining():
    a = Node(name="a", id="a", original_data=b"A")
    b = Node(name="b", id="b", original_data=b"B")
    z = Node(name="z", id="z", original_data=b"Z")
    doc = Document(Node(name="root", id="root", is_folder=True, children=(z, a, b)))
    d1 = apply(doc, Merge(("a", "b")), ENGINE)
    # merged is a new node (new id) named after the first; it sits in a's slot.
    assert [k.name for k in d1.root.children] == ["z", "a"]
    assert d1.root.children[1].original_data == b"A|B"


def test_merge_same_dpi_keeps_compression():
    d1 = apply(
        merge_doc(
            a_kw=dict(is_compressed=True, dpi_current=150, current_data=b"ca"),
            b_kw=dict(is_compressed=True, dpi_current=150, current_data=b"cb"),
        ),
        Merge(("a", "b")), ENGINE)
    merged = d1.root.children[0]
    assert merged.is_compressed is True and merged.dpi_current == 150
    assert merged.current_data == b"ca|cb"


def test_merge_dpi_conflict_drops_compression():
    d1 = apply(
        merge_doc(
            a_kw=dict(is_compressed=True, dpi_current=100, current_data=b"ca"),
            b_kw=dict(is_compressed=True, dpi_current=200, current_data=b"cb"),
        ),
        Merge(("a", "b")), ENGINE)
    merged = d1.root.children[0]
    assert merged.no_compression is True
    assert merged.is_compressed is False
    assert merged.dpi_current is None and merged.current_data is None


def test_merge_mixed_compression_is_uncompressed():
    d1 = apply(
        merge_doc(a_kw=dict(is_compressed=True, dpi_current=150, current_data=b"ca")),
        Merge(("a", "b")), ENGINE)
    merged = d1.root.children[0]
    assert merged.is_compressed is False and merged.current_data is None
    assert merged.no_compression is False


def test_merge_propagates_no_compression():
    d1 = apply(merge_doc(a_kw=dict(no_compression=True)), Merge(("a", "b")), ENGINE)
    assert d1.root.children[0].no_compression is True


def test_merge_errors():
    with pytest.raises(CommandError):
        apply(merge_doc(), Merge(("a",)), ENGINE)                    # < 2
    with pytest.raises(CommandError):
        apply(merge_doc(), Merge(("a", "root")), ENGINE)            # folder, not leaf
    with pytest.raises(CommandError):
        apply(merge_doc(), Merge(("a", "missing")), ENGINE)
    with pytest.raises(CommandError):
        apply(merge_doc(), Merge(("a", "b")))                       # no engine
    # different parents
    inner = Node(name="b", id="b", original_data=b"B")
    f = Node(name="f", id="f", is_folder=True, children=(inner,))
    a = Node(name="a", id="a", original_data=b"A")
    doc = Document(Node(name="root", id="root", is_folder=True, children=(a, f)))
    with pytest.raises(CommandError):
        apply(doc, Merge(("a", "b")), ENGINE)


# --- serialisation ---------------------------------------------------------

def test_split_merge_serialisation_roundtrip():
    assert command_from_dict(command_to_dict(Split("a"))) == Split("a")
    m = Merge(("a", "b"))
    back = command_from_dict(command_to_dict(m))
    assert back == m and isinstance(back.node_ids, tuple)
