"""Integration tests: RealEngine + commands on actual PDFs."""

from core.engine import RealEngine
from core.model import Document, Node
from core.commands import Compress, Rotate, apply
from helpers import create_valid_pdf

ENGINE = RealEngine()


def leaf_doc(data) -> Document:
    leaf = Node(name="a", id="a", pdf_length=1, original_data=data)
    return Document(Node(name="root", id="root", is_folder=True, children=(leaf,)))


def test_real_page_count():
    assert ENGINE.page_count(create_valid_pdf(pages=3)) == 3


def test_real_engine_caches_compression(monkeypatch):
    # re-selecting a node must not recompute its compressions: compress_all_methods
    # runs once per (content, dpi), then the cache serves compress + compress_methods.
    from formats import compress_pdf_bytes
    calls = []
    orig = compress_pdf_bytes.compress_all_methods
    monkeypatch.setattr(compress_pdf_bytes, "compress_all_methods",
                        lambda b, dpi, cancel=None: (calls.append(1), orig(b, dpi=dpi, cancel=cancel))[1])
    eng = RealEngine()
    data = create_valid_pdf(pages=2)
    eng.compress_methods(data, 150)
    eng.compress(data, 150, None)
    eng.compress_methods(data, 150)
    assert len(calls) == 1                       # computed once, then cached
    eng.compress_methods(data, 120)              # different DPI → recompute
    assert len(calls) == 2


def test_real_compress_reduces_size():
    data = create_valid_pdf(pages=1)  # the compressible sample fixture
    out = ENGINE.compress(data, dpi=150)
    assert out is not None and len(out) < len(data)


def test_real_rotate_preserves_page_count_and_changes_bytes():
    data = create_valid_pdf(pages=2)
    rotated = ENGINE.rotate(data, 90)
    assert ENGINE.page_count(rotated) == 2
    assert rotated != data


def test_real_split_and_merge_roundtrip_page_counts():
    data = create_valid_pdf(pages=3)
    parts = ENGINE.split(data)
    assert len(parts) == 3 and all(ENGINE.page_count(p) == 1 for p in parts)
    merged = ENGINE.merge(parts)
    assert ENGINE.page_count(merged) == 3


def test_compress_command_with_real_engine():
    d1 = apply(leaf_doc(create_valid_pdf(pages=1)), Compress("a", dpi=150), ENGINE)
    a = d1.find("a")
    assert a.is_compressed is True and a.dpi_current == 150
    assert a.current_data is not None and len(a.current_data) < len(a.original_data)


def test_compress_methods_and_explicit_method():
    data = create_valid_pdf(pages=1)
    sizes = ENGINE.compress_methods(data, 150)
    assert sizes and all(s < len(data) for s in sizes.values())
    method = min(sizes, key=sizes.get)  # smallest = best
    d1 = apply(leaf_doc(data), Compress("a", dpi=150, method=method), ENGINE)
    a = d1.find("a")
    assert a.is_compressed is True and a.dpi_current == 150 and a.current_data is not None


def test_rotate_command_with_real_engine():
    d1 = apply(leaf_doc(create_valid_pdf(pages=1)), Rotate("a", "right"), ENGINE)
    a = d1.find("a")
    assert ENGINE.page_count(a.original_data) == 1
    assert a.current_data is None  # compression invalidated
