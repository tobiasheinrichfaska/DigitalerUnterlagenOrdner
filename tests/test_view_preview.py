import pytest
import tkinter as tk
from view_preview import PreviewFrame
from pdf_node import PDFNode
from PIL import Image
import os
from helpers import create_valid_pdf, wait_for_real_preview

pytestmark = pytest.mark.skipif(
    "DISPLAY" not in os.environ and os.name != "nt",
    reason="Kein X-Server (Linux) oder GUI-Umgebung (macOS) verfügbar"
)


class DummyController:
    def __init__(self):
        self.updated = False
    def update_preview(self, node):
        self.updated = True

@pytest.fixture
def preview():
    root = tk.Tk()
    ctrl = DummyController()
    frame = PreviewFrame(root, controller=ctrl)
    frame.pack()
    yield frame
    frame.destroy()
    root.destroy()

def minimal_node():
    img = Image.new("RGB", (100, 100), color="white")
    node = PDFNode("Test", pdf_data=b"%PDF-1.4\n%EOF")
    node._original_preview_images = [img]
    node._current_preview_images = [img]
    node.original_pdf_data = b"%PDF-1.4\n%EOF"
    node.current_pdf_data = b"%PDF-1.4\n%EOF"
    return node


def test_reset_compression():
    # PDF mit 1 Seite erzeugen und komprimieren
    data = create_valid_pdf(pages=1)
    node = PDFNode("test_reset", pdf_data=data)
    wait_for_real_preview(node)
    
    assert node.is_compressed is True
    assert node.current_pdf_data is not None

    # Rücksetzen der Kompression
    node.reset_compression()

    # Prüfen: Komprimierung zurückgesetzt
    assert node.is_compressed is False
    assert node._current_pdf_data is None
    assert node._current_preview_pages == []  # explizit leer


def test_slider_release_triggers_update(preview):
    node = minimal_node()
    node.dpi_original = 100
    preview.current_node = node
    preview.slider.set(90)

    # monkeypatch Kompression zur Vermeidung des echten Aufrufs
    node.compress = lambda dpi: setattr(node, "dpi_current", dpi)

    preview._on_slider_released(None)
    assert node.dpi_current == 90

def test_on_zoom_changed(preview):
    preview._on_zoom_changed("150")
    assert preview.zoom_level == 1.5