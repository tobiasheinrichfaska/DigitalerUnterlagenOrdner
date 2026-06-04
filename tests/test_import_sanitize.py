"""sanitize_pdf is wired back into the plain-PDF import path (PDF auto-repair),
but must never touch the /JSONStructure (.belegtool) path."""

import pytest

import pdf_storage
from pdf_storage import PDFStorage
from core.bridge import save_belegtool, load_belegtool
from core.model import Document, Node
from helpers import create_valid_pdf


def _write(tmp_path, data, name="in.pdf"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_plain_pdf_import_routes_through_sanitize(tmp_path, monkeypatch):
    """The imported node carries sanitize_pdf's OUTPUT, not the raw input —
    proof the repair step is actually in the data path."""
    replacement = create_valid_pdf(pages=2)  # what "repair" returns
    called = {"n": 0}

    def fake_sanitize(data):
        called["n"] += 1
        return replacement

    monkeypatch.setattr(pdf_storage, "sanitize_pdf", fake_sanitize)

    storage = PDFStorage(_write(tmp_path, create_valid_pdf(pages=1)))
    leaf = storage.root.children[0]
    assert called["n"] == 1
    assert leaf.pdf_length == 2                       # got the repaired 2-page bytes
    assert leaf.original_pdf_data == replacement


def test_valid_pdf_passes_through_unchanged(tmp_path):
    """sanitize_pdf is a no-op on a readable PDF → bytes survive verbatim."""
    data = create_valid_pdf(pages=3)
    storage = PDFStorage(_write(tmp_path, data))
    leaf = storage.root.children[0]
    assert leaf.original_pdf_data == data
    assert leaf.pdf_length == 3


def test_belegtool_reload_never_sanitizes(tmp_path, monkeypatch):
    """The /JSONStructure path must not run sanitize_pdf (it could drop the
    metadata / re-slice). Reload must succeed without ever calling it."""
    doc = Document(Node(name="root", is_folder=True, children=(
        Node(name="doc1", pdf_length=1, no_compression=True,
             original_data=create_valid_pdf(pages=1)),
        Node(name="OrdnerA", is_folder=True, children=(
            Node(name="doc2", pdf_length=2, no_compression=True,
                 original_data=create_valid_pdf(pages=2)),)),
    )))
    path = tmp_path / "out.belegtool"
    save_belegtool(doc, path)

    def boom(data):
        raise AssertionError("sanitize_pdf must not run on the .belegtool path")

    monkeypatch.setattr(pdf_storage, "sanitize_pdf", boom)

    loaded = load_belegtool(path)  # would raise via boom if it sanitized
    names = [c.name for c in loaded.root.children]
    assert names == ["doc1", "OrdnerA"]
