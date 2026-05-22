import io
from pdf_node import PDFNode
from helpers import wait_for_real_preview


def create_dummy_pdf(pages: int = 1) -> bytes:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()

def create_node_with_preview(name, pages=1, dpi_original=150, dpi_current=120):
    data = create_dummy_pdf(pages)
    node = PDFNode(name=name, pdf_data=data)
    node.dpi_original = dpi_original
    node.dpi_current = dpi_current
    node.is_compressed = True
    node.no_compression = False
    node.update_preview()
    return node


def test_merge_pdf_nodes_combines_pages_and_previews():
    node1 = create_node_with_preview("A", pages=1)
    node2 = create_node_with_preview("B", pages=2)

    # Vor Merge
    assert node1.pdf_length == 1
    assert len(node1.current_preview_images) == 1
    assert len(node2.current_preview_images) == 2

    # Merge ohne sofortige Vorschau
    node1.merge(node2, nopreview=True)

    # Manuell Vorschau aktualisieren
    node1.update_preview()
    wait_for_real_preview(node1)

    # Nach Merge: 3 Seiten, kombinierte Vorschau
    assert node1.pdf_length == 3
    assert len(node1.current_preview_images) == 3
    assert len(node1.original_preview_images) == 3
    assert node1.dpi_original == 150
    assert node1.dpi_current == 120
    assert node1.is_compressed is True
    assert node1.no_compression is False
