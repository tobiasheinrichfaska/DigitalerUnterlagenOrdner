import pytest
from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_real_preview


def make_leaf(name="leaf"):
    return PDFNode(name=name, pdf_data=create_valid_pdf(pages=1))


def test_copy_default_appends_suffix():
    node = make_leaf("original")
    copied = node.copy()
    assert copied.name == "original_copy"


def test_copy_keep_name_preserves_name():
    node = make_leaf("mydoc")
    copied = node.copy(keep_name=True)
    assert copied.name == "mydoc"


def test_copy_preserves_pdf_data():
    node = make_leaf("data_node")
    copied = node.copy(keep_name=True)
    assert copied.original_pdf_data == node.original_pdf_data
    assert copied.current_pdf_data == node.current_pdf_data


def test_copy_data_is_independent():
    node = make_leaf("independent")
    copied = node.copy(keep_name=True)
    original_data = node.original_pdf_data
    node.original_pdf_data = b"changed"
    assert copied.original_pdf_data == original_data


def test_copy_preserves_metadata():
    node = make_leaf("meta")
    node.status = "erfasst"
    node.no_compression = True
    node.dpi_original = 150
    node.dpi_current = 100

    copied = node.copy(keep_name=True)
    assert copied.status == "erfasst"
    assert copied.no_compression is True
    assert copied.dpi_original == 150
    assert copied.dpi_current == 100


def test_copy_folder_recursive_keep_name():
    folder = PDFNode("Ordner", is_folder=True)
    child1 = make_leaf("Kind1")
    child2 = make_leaf("Kind2")
    folder.add_child(child1)
    folder.add_child(child2)

    copied = folder.copy(keep_name=True)
    assert copied.name == "Ordner"
    assert len(copied.children) == 2
    assert copied.children[0].name == "Kind1"
    assert copied.children[1].name == "Kind2"


def test_copy_folder_recursive_without_keep_name():
    folder = PDFNode("Ordner", is_folder=True)
    child = make_leaf("Kind")
    folder.add_child(child)

    copied = folder.copy()
    assert copied.name == "Ordner_copy"
    assert copied.children[0].name == "Kind_copy"


def test_copy_has_distinct_uid():
    node = make_leaf("uid_test")
    copied = node.copy(keep_name=True)
    assert copied.uid != node.uid


def test_copy_parent_not_set():
    folder = PDFNode("parent", is_folder=True)
    child = make_leaf("child")
    folder.add_child(child)

    copied_child = child.copy(keep_name=True)
    assert copied_child.parent is None
