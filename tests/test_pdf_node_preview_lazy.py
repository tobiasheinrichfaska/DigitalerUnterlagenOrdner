import io
import time
from pathlib import Path
from pdf_node import PDFNode
from tools import PLACEHOLDER_PREVIEW

def test_lazy_preview_uses_placeholder():
    # Beispiel-PDF laden
    pdf_path = Path("tests/data/input/sample.pdf")
    with open(pdf_path, "rb") as f:
        data = f.read()

    node = PDFNode(name="LazyPreviewTest", pdf_data=data)

    # Leere Previews setzen und Lazy-Vorschau starten
    node._current_preview_images = []
    node._original_preview_images = []
    node.preview_lazy()

    # Direkt nach Start sollte Task laufen
    assert node._preview_task_running is True

    # Zugriff auf Vorschau sollte jetzt den Platzhalter liefern
    current = node.current_preview_images
    assert len(current) == 1
    assert current[0] is PLACEHOLDER_PREVIEW

    # Nach Abschluss: Vorschau sollte ersetzt sein
    time.sleep(3)  # Warten auf Thread-Ende
    assert node._preview_task_running is False
    final = node.current_preview_images
    assert final[0] is not PLACEHOLDER_PREVIEW
    assert len(final) >= 1
