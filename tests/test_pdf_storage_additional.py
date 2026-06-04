
import io
import tempfile
import os
import pytest
from pdf_storage import PDFStorage
from pdf_node import PDFNode
from helpers import create_valid_pdf

def test_mark_and_clear_dirty():
    storage = PDFStorage()
    assert not storage.is_dirty
    storage.mark_dirty()
    assert storage.is_dirty
    storage.clear_dirty()
    assert not storage.is_dirty

def test_extract_pages():
    # Erzeuge ein valides PDF mit mindestens einer Seite
    pdf_data = create_valid_pdf(pages=2)

    # Extrahiere die erste Seite (Index 0)
    out = PDFStorage.extract_pages(pdf_data, 0, 0)

    # Prüfungen auf Grundstruktur
    assert out.startswith(b"%PDF")
    assert b"/Page" in out


def test_save_creates_file(tmp_path):
    storage = PDFStorage()
    node = PDFNode("to_save", pdf_data=create_valid_pdf(pages=1))
    storage.root.add_child(node)
    target = tmp_path / "testout.pdf"
    storage.save(str(target))
    assert target.exists()
    content = target.read_bytes()
    assert b"%PDF" in content
    assert b"/JSONStructure" in content


def test_get_all_nodes():
    storage = PDFStorage()
    a = PDFNode("A", is_folder=True)
    b = PDFNode("B", pdf_data=create_valid_pdf(pages=1))
    a.add_child(b)
    storage.root.add_child(a)
    nodes = storage.get_all_nodes()
    names = [n.name for n in nodes]
    assert "A" in names and "B" in names


def test_get_structure_json():
    storage = PDFStorage()
    node = PDFNode("testnode", pdf_data=create_valid_pdf(pages=1))
    storage.root.add_child(node)
    json_str = storage.get_structure_json()
    assert '"name": "testnode"' in json_str
    assert '"children": []' in json_str


def test_perform_move_and_gui_plan():
    storage = PDFStorage()
    folder = PDFNode("folder", is_folder=True)
    node = PDFNode("moveme", pdf_data=create_valid_pdf(pages=1))
    storage.root.add_child(node)
    storage.root.add_child(folder)
    gui_plan = storage.perform_move([node], folder)
    assert isinstance(gui_plan, list)
    assert any(entry["uid"] == node.uid for entry in gui_plan)

