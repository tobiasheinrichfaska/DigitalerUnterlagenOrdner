from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_real_preview

def test_set_original_and_current_triggers_lazy():
    # Valides Test-PDF mit einer Seite direkt einfügen
    data = create_valid_pdf(pages=1)
    node = PDFNode("test_lazy.pdf", pdf_data=data)

    wait_for_real_preview(node)

    # Erwartung: Kompression wurde automatisch mit dpi=120 ausgeführt
    assert node.dpi_current == 120
    assert node.is_compressed is True
    assert node._current_pdf_data is not None
