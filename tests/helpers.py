import io
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pdf_node import PDFNode
import time
from tools import PLACEHOLDER_PREVIEW



def create_valid_pdf(pages=1) -> bytes:
    sample_path = Path("tests/data/input/sample.pdf")
    
    # ✅ Versuche sample.pdf zu laden
    if sample_path.exists():
        try:
            with open(sample_path, "rb") as f:
                reader = PdfReader(f)
                writer = PdfWriter()
                for i, page in enumerate(reader.pages):
                    writer.add_page(page)
                    if i + 1 >= pages:
                        break
                buffer = io.BytesIO()
                writer.write(buffer)
                return buffer.getvalue()
        except Exception as e:
            print(f"[WARN] Konnte sample.pdf nicht verwenden: {e}")

    # 🔁 Fallback: leeres valides PDF erzeugen
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()



def create_test_node(name="TestNode", pages=1) -> PDFNode:
    return PDFNode(name=name, pdf_data=create_valid_pdf(pages))

def wait_for_real_preview(node, timeout=20):
    import time
    from tools import PLACEHOLDER_PREVIEW

    start = time.time()
    while time.time() - start < timeout:
        imgs = node.current_preview_images
        # ❗ Sicherstellen, dass aktuelle Vorschau und Daten vollständig sind
        if (
            imgs
            and all(img != PLACEHOLDER_PREVIEW for img in imgs)
            and node.current_pdf_data is not None
            and node.dpi_current is not None
        ):
            return imgs
        time.sleep(0.1)

    raise TimeoutError("Vorschau oder Kompression nicht abgeschlossen")


def wait_for_compression(node: PDFNode, timeout: float = 20.0):
    """
    Wartet synchron darauf, dass die Kompression vollständig abgeschlossen ist.
    Bricht nach `timeout` Sekunden mit TimeoutError ab.
    """
    import time
    start = time.time()

    while node._compression_task_running:
        if time.time() - start > timeout:
            raise TimeoutError("Kompression nicht abgeschlossen (Timeout)")
        time.sleep(0.05)  # 50 ms warten

def wait_for_ready(node: PDFNode, timeout: float = 20.0):
    """
    Wartet, bis Vorschau **und** Kompression abgeschlossen sind.
    """
    import time
    start = time.time()

    while node._preview_task_running or node._compression_task_running:
        if time.time() - start > timeout:
            raise TimeoutError("Preview oder Kompression nicht abgeschlossen")
        time.sleep(0.05)

