import pytest
from pdf_storage import PDFStorage
from pdf_node import PDFNode
from helpers import create_valid_pdf


def test_add_node_and_retrieve():
    storage = PDFStorage()
    valid_data = create_valid_pdf(pages=1)
    node = PDFNode("A", pdf_data=valid_data)
    storage.root.add_child(node)
    assert node in storage.root.children


def test_storage_root_to_dict():
    storage = PDFStorage()
    valid_data = create_valid_pdf(pages=1)
    node = PDFNode("B", pdf_data=valid_data)
    storage.root.add_child(node)
    data = storage.root.to_dict()
    assert "children" in data
    assert any(child["name"] == "B" for child in data["children"])
