import io
import pytest
from pypdf import PdfReader
from formats.pdf_storage import PDFStorage
from formats.pdf_node import PDFNode
from formats.toc_export import empty_leaf_names
from helpers import create_valid_pdf


def build_storage():
    """Returns a storage with: root -> folder -> [doc1(2p), doc2(1p)]"""
    storage = PDFStorage()
    folder = PDFNode("Ordner", is_folder=True)
    doc1 = PDFNode("Dok1", pdf_data=create_valid_pdf(pages=2))
    doc2 = PDFNode("Dok2", pdf_data=create_valid_pdf(pages=1))
    folder.add_child(doc1)
    folder.add_child(doc2)
    storage.root.add_child(folder)
    return storage, folder, doc1, doc2


def page_count(path):
    data = open(path, "rb").read()
    return len(PdfReader(io.BytesIO(data)).pages)


# --- .pdf export ---

def test_export_single_leaf_as_pdf(tmp_path):
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "out.pdf")
    storage.export_selection([doc1], out)
    assert page_count(out) == 2


def test_export_multiple_leaves_as_pdf(tmp_path):
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "out.pdf")
    storage.export_selection([doc1, doc2], out)
    assert page_count(out) == 3


def test_export_folder_as_pdf(tmp_path):
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "out.pdf")
    storage.export_selection([folder], out)
    assert page_count(out) == 3


def test_export_parent_child_conflict_resolved_as_pdf(tmp_path):
    """When folder and its child are both selected, folder takes precedence (all 3 pages)."""
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "out.pdf")
    storage.export_selection([folder, doc1], out)
    assert page_count(out) == 3


# --- .belegtool export ---

def test_export_single_leaf_as_belegtool(tmp_path):
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "export.belegtool")
    storage.export_selection([doc1], out)

    with open(out, "rb") as f:
        content = f.read()
    assert b"%PDF" in content
    assert b"/JSONStructure" in content


def test_export_belegtool_reloadable(tmp_path):
    storage, folder, doc1, doc2 = build_storage()
    out = str(tmp_path / "export.belegtool")
    storage.export_selection([doc1, doc2], out)

    reloaded = PDFStorage(out)
    leaf_names = [n.name for n in reloaded.get_all_nodes() if not n.is_folder]
    assert "Dok1" in leaf_names
    assert "Dok2" in leaf_names


def test_export_empty_selection_produces_empty_pdf(tmp_path):
    storage, _, doc1, _ = build_storage()
    out = str(tmp_path / "out.pdf")
    storage.export_selection([], out)
    assert page_count(out) == 0


# --- skipped empty-leaf detection (drives the export warning channel) ---

def test_empty_leaf_names_reports_only_pageless_leaves():
    folder = PDFNode("Ordner", is_folder=True)
    real = PDFNode("Dok1", pdf_data=create_valid_pdf(pages=1))
    empty = PDFNode("Leer")  # no pdf_data → 0 pages
    folder.add_child(real)
    folder.add_child(empty)
    assert empty_leaf_names([folder]) == ["Leer"]  # recurses; folders not reported


def test_empty_leaf_names_empty_when_all_have_pages():
    real = PDFNode("Dok1", pdf_data=create_valid_pdf(pages=1))
    assert empty_leaf_names([real]) == []
