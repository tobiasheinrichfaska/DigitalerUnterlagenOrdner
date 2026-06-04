"""A plain PDF must import as a single leaf node, not folder -> pdf."""

from formats.pdf_storage import PDFStorage, create_wrapper_node
from formats.pdf_node import PDFNode
from helpers import create_valid_pdf


def _storage_with_children(children):
    storage = PDFStorage.__new__(PDFStorage)  # bypass file loading
    storage.root = PDFNode(name="root", is_folder=True)
    for c in children:
        storage.root.add_child(c)
    return storage


def test_single_pdf_is_not_wrapped_in_a_folder():
    pdf = PDFNode(name="rechnung", pdf_data=create_valid_pdf(pages=1))
    storage = _storage_with_children([pdf])

    node = create_wrapper_node(storage, "rechnung.pdf")

    assert node is pdf
    assert node.is_folder is False


def test_multiple_top_level_nodes_are_wrapped():
    a = PDFNode(name="a", pdf_data=create_valid_pdf(pages=1))
    b = PDFNode(name="b", pdf_data=create_valid_pdf(pages=1))
    storage = _storage_with_children([a, b])

    node = create_wrapper_node(storage, "bundle.pdf")

    assert node.is_folder is True
    assert node.name == "bundle"
    assert {c.name for c in node.children} == {"a", "b"}


def test_matching_top_folder_is_not_double_wrapped():
    inner = PDFNode(name="archiv", is_folder=True)
    inner.add_child(PDFNode(name="x", pdf_data=create_valid_pdf(pages=1)))
    storage = _storage_with_children([inner])

    node = create_wrapper_node(storage, "archiv.zip")

    assert node is inner
    assert node.is_folder is True


def test_load_plain_pdf_yields_single_leaf():
    # End-to-end: PDFStorage loading a PDF byte stream produces one leaf child.
    storage = PDFStorage(create_valid_pdf(pages=2))
    assert len(storage.root.children) == 1
    assert storage.root.children[0].is_folder is False


def test_empty_app_import_single_pdf_no_error(tmp_path):
    # Mirrors the import flow when the app starts EMPTY and one PDF is imported:
    #   storage is None -> create empty PDFStorage(); load the file; wrap; add.
    pdf_path = tmp_path / "rechnung.pdf"
    pdf_path.write_bytes(create_valid_pdf(pages=1))

    app_storage = PDFStorage()                 # fresh empty app (no source)
    assert app_storage.root.children == []

    temp_storage = PDFStorage(str(pdf_path))   # load the chosen PDF
    wrapper = create_wrapper_node(temp_storage, str(pdf_path))
    app_storage.root.add_child(wrapper)        # what import_pdf / drop does

    # Result: exactly one node, a leaf — no folder wrapper, no error.
    assert len(app_storage.root.children) == 1
    assert app_storage.root.children[0] is wrapper
    assert wrapper.is_folder is False
    assert wrapper.parent is app_storage.root
