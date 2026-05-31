"""Tests for the Document <-> PDFStorage / .belegtool bridge (D5)."""

import io

from pypdf import PdfReader

from core.bridge import (
    document_from_storage,
    document_to_storage,
    load_belegtool,
    save_belegtool,
)
from core.model import Document, Node
from helpers import create_valid_pdf


def _strip_ids(d: dict) -> dict:
    d = dict(d)
    d.pop("id", None)
    d["children"] = [_strip_ids(c) for c in d["children"]]
    return d


def _page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def _by_name(doc: Document, name: str):
    for n in doc.root.iter():
        if n.name == name:
            return n
    return None


# --- in-memory round-trip (full fidelity, ids preserved) -------------------

def test_storage_roundtrip_preserves_everything():
    leaf = Node(
        name="doc1", id="leaf1", pdf_length=2,
        original_data=b"ORIG", current_data=b"CURR",
        is_compressed=True, dpi_original=300, dpi_current=150,
        status="erfasst", vz_start=2023, vz_end=2024,
    )
    split_part = Node(name="p1", id="p1", pdf_length=1,
                      original_data=b"P1", no_compression=True)
    folder = Node(name="OrdnerA", id="f", is_folder=True, children=(split_part,))
    doc = Document(Node(name="root", id="root", is_folder=True, children=(leaf, folder)))

    back = document_from_storage(document_to_storage(doc))
    assert back.to_dict() == doc.to_dict()  # ids preserved via uid

    # bytes survive on the leaves; the folder carries none
    assert back.find("leaf1").original_data == b"ORIG"
    assert back.find("leaf1").current_data == b"CURR"
    assert back.find("f").original_data is None


# --- real .belegtool file round-trip ---------------------------------------

def test_belegtool_file_roundtrip(tmp_path):
    # no_compression leaves: PDFStorage auto-runs lazy compression on *un*compressed
    # leaves when loading, which would non-deterministically flip the flags. Marking
    # them no_compression keeps the flag round-trip deterministic (split-part case).
    leaf1 = Node(name="doc1", pdf_length=1, no_compression=True,
                 original_data=create_valid_pdf(pages=1))
    leaf2 = Node(name="doc2", pdf_length=2, no_compression=True,
                 original_data=create_valid_pdf(pages=2))
    folder = Node(name="OrdnerA", is_folder=True, children=(leaf2,))
    doc = Document(Node(name="root", is_folder=True, children=(leaf1, folder)))

    path = tmp_path / "out.belegtool"
    save_belegtool(doc, path)
    loaded = load_belegtool(path)

    # structure + flags survive (ids are not stored in the file → ignore them)
    assert _strip_ids(loaded.to_dict()) == _strip_ids(doc.to_dict())

    # page data comes back as real PDFs with the right page counts
    d1 = _by_name(loaded, "doc1")
    d2 = _by_name(loaded, "doc2")
    assert d1.original_data.startswith(b"%PDF") and _page_count(d1.original_data) == 1
    assert _page_count(d2.original_data) == 2
