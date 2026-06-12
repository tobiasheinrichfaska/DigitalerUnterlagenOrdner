import pytest
from formats.pdf_storage import PDFStorage
from formats.pdf_node import PDFNode
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


def _belegtool_with_structure(structure: dict) -> bytes:
    """A .belegtool PDF (one blank page) carrying an arbitrary /JSONStructure tree."""
    import io
    import json
    from pypdf import PdfWriter
    from helpers import create_valid_pdf
    reader_src = create_valid_pdf(pages=1)
    writer = PdfWriter()
    from pypdf import PdfReader
    for p in PdfReader(io.BytesIO(reader_src)).pages:
        writer.add_page(p)
    writer.add_metadata({"/JSONStructure": json.dumps(structure)})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_deeply_nested_structure_is_refused():
    # Build a 250-level-deep folder chain — past _MAX_TREE_DEPTH (200). Loading it
    # must fail cleanly instead of risking a recursion blow-up in to_dict/export later.
    from formats.pdf_storage import _MAX_TREE_DEPTH
    node = {"name": "leaf", "is_folder": True, "children": []}
    for _ in range(_MAX_TREE_DEPTH + 50):
        node = {"name": "f", "is_folder": True, "children": [node]}
    structure = {"name": "root", "is_folder": True, "children": [node]}
    data = _belegtool_with_structure(structure)
    with pytest.raises(ValueError):
        PDFStorage(data)


def test_shallow_structure_still_loads():
    structure = {"name": "root", "is_folder": True, "children": [
        {"name": "f", "is_folder": True, "children": [
            {"name": "g", "is_folder": True, "children": []},
        ]},
    ]}
    data = _belegtool_with_structure(structure)
    storage = PDFStorage(data)  # well under the cap → loads fine
    assert storage.root.children
