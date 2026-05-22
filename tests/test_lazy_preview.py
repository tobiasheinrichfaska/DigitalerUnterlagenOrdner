from pdf_node import PDFNode
from helpers import create_valid_pdf, wait_for_real_preview
import time

def test_preview_lazy_stacks_only_latest():
    node = PDFNode("lazytest", pdf_data=create_valid_pdf(pages=1))

    # Zwei schnelle Vorschauanforderungen → nur eine darf vorgemerkt sein
    node.preview_lazy()
    time.sleep(0.05)  # Zeit für ersten Thread zum Starten
    node.preview_lazy()  # löst Task-Vormerkung aus
    node.preview_lazy()  # ersetzt Vormerkung nicht erneut

    # Während Task läuft → requested = True
    assert node._preview_task_running is True
    assert node._preview_task_requested is True

    wait_for_real_preview(node)

    # Nach Abschluss: nichts mehr vorgemerkt
    assert node._preview_task_running is False
    assert node._preview_task_requested is False
