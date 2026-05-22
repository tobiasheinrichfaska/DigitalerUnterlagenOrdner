import pytest
from pdf_node import PDFNode

def test_from_pdf_invalid_type():
    with pytest.raises(TypeError):
        PDFNode.from_pdf("bad", 12345)

def test_create_preview_invalid_pdf():
    broken_pdf = b"Not a PDF at all"
    node = PDFNode("broken", pdf_data=None)

    result = node._create_previews(broken_pdf)

    assert result == []


def test_merge_type_conflict():
    a = PDFNode("a", is_folder=True)
    b = PDFNode("b", is_folder=False, pdf_data=b"%PDF-1.4\n%%EOF")
    with pytest.raises(ValueError):
        a.merge(b)

def test_merge_invalid_pdf():
    a = PDFNode("a", pdf_data=b"%PDF-1.4\n%%EOF")
    b = PDFNode("b", pdf_data=b"defekt")
    with pytest.raises(ValueError):
        a.merge(b)