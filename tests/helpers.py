import io
from pathlib import Path
from pypdf import PdfReader, PdfWriter


def create_valid_pdf(pages=1) -> bytes:
    sample_path = Path("tests/data/input/sample.pdf")

    # Versuche sample.pdf zu laden
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

    # Fallback: leeres valides PDF erzeugen
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
