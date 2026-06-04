
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



