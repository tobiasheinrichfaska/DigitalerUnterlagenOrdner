"""Regression tests for PDFNode folder data aggregation.

A folder's ``current_pdf_data`` / ``original_pdf_data`` must aggregate the
*effective* data of every child, including:
  - leaves that are not (yet) compressed (``_current_pdf_data is None``),
  - ``no_compression`` leaves such as split nodes,
  - nested sub-folders.

Previously the folder read the children's private ``_current_pdf_data``
attribute directly, which silently dropped all of the above and left the
folder reporting ``is_valid() == False`` / missing pages.
"""

from pypdf import PdfReader
import io

from pdf_node import PDFNode
from helpers import create_valid_pdf


def _page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def test_folder_current_data_includes_uncompressed_leaf():
    folder = PDFNode("folder", is_folder=True)
    leaf = PDFNode("leaf", pdf_data=create_valid_pdf(pages=1))
    leaf.no_compression = True          # like a split node: never gets _current_pdf_data
    leaf.current_pdf_data = None
    folder.add_child(leaf)

    assert folder.is_valid(), "Folder with a no_compression leaf must be valid"
    assert _page_count(folder.current_pdf_data) == 1


def test_folder_aggregates_all_children_pages():
    folder = PDFNode("folder", is_folder=True)
    folder.add_child(PDFNode("a", pdf_data=create_valid_pdf(pages=1)))
    folder.add_child(PDFNode("b", pdf_data=create_valid_pdf(pages=2)))
    assert _page_count(folder.current_pdf_data) == 3
    assert _page_count(folder.original_pdf_data) == 3


def test_nested_folder_data_recurses():
    inner = PDFNode("inner", is_folder=True)
    inner.add_child(PDFNode("x", pdf_data=create_valid_pdf(pages=2)))

    outer = PDFNode("outer", is_folder=True)
    outer.add_child(PDFNode("y", pdf_data=create_valid_pdf(pages=1)))
    outer.add_child(inner)

    # 1 (y) + 2 (inner/x) — the nested folder must not be dropped.
    assert _page_count(outer.current_pdf_data) == 3
    assert _page_count(outer.original_pdf_data) == 3
