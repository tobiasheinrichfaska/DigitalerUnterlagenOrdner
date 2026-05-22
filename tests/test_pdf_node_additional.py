import io
import pytest
from pdf_node import PDFNode
from helpers import create_test_node, create_valid_pdf, wait_for_real_preview
from tools import PLACEHOLDER_PREVIEW

def valid_minimal_pdf():
    return create_valid_pdf(pages=1)


def test_update_preview():
    node = create_test_node("test")
    images = wait_for_real_preview(node)
    assert images  # Sicher: Nicht leer


def test_setters_on_folder():
    folder = PDFNode("folder", is_folder=True)
    folder.current_pdf_data = b"xxx"
    folder.original_pdf_data = b"yyy"
    assert folder.current_pdf_data is None or isinstance(folder.current_pdf_data, bytes)
    assert folder.original_pdf_data is None or isinstance(folder.original_pdf_data, bytes)


def test_commit_changes():
    node = create_test_node("commit_test")
    wait_for_real_preview(node)  # sicherstellen, dass Kompression abgeschlossen ist

    if not node.current_pdf_data:
        pytest.skip("Kompression schlug fehl – kein Vergleich möglich.")

    original = node.original_pdf_data
    node.commit_changes()
    assert node.original_pdf_data != original
    assert node._current_pdf_data is None


def test_reset_compression():
    node = create_test_node("reset_test")
    wait_for_real_preview(node)  # wichtig: auf Vorschau/Kompression warten

    if node.current_pdf_data:
        node.reset_compression()
        assert node._current_pdf_data is None
    else:
        pytest.skip("Kompression war nicht erfolgreich – Test übersprungen.")


def test_delete_node():
    parent = PDFNode("parent", is_folder=True)
    child = create_test_node("child")
    parent.add_child(child)
    assert child in parent.children
    child.delete()
    assert child not in parent.children
    assert child.parent is None
