import io
from pdf_node import PDFNode
from pypdf import PdfWriter

def create_valid_pdf(pages=1) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()

def test_split_folder_node():
    # Erstelle gültige Kinder mit echter PDF-Seite
    child1 = PDFNode(name="Kind1", pdf_data=create_valid_pdf())
    child2 = PDFNode(name="Kind2", pdf_data=create_valid_pdf())
    child3 = PDFNode(name="Kind3", pdf_data=create_valid_pdf())

    folder = PDFNode(name="Ordner", is_folder=True)
    folder.add_child(child1)
    folder.add_child(child2)
    folder.add_child(child3)

    assert len(folder.children) == 3

    # Split aufrufen
    new_nodes = folder.split()

    # Der ursprüngliche Ordner sollte nur noch ein Kind enthalten
    assert len(folder.children) == 1
    assert folder.children[0].name == "Kind1"

    # Die neuen Ordnerknoten sollten jeweils genau 1 Kind haben
    for new_folder in new_nodes:
        assert new_folder.is_folder
        assert len(new_folder.children) == 1
        assert new_folder.children[0].name in ("Kind2", "Kind3")
        assert new_folder.children[0].parent == new_folder
