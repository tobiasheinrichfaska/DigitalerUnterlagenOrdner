import time
from pathlib import Path
from pdf_node import PDFNode

def valid_minimal_pdf():
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 72 720 Td (Hello World) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000061 00000 n
0000000120 00000 n
0000000201 00000 n
trailer << /Size 5 /Root 1 0 R >>
startxref
269
%%EOF"""

# PDFNodes erstellen
a = PDFNode("a", pdf_data=valid_minimal_pdf())
b = PDFNode("b", pdf_data=valid_minimal_pdf())

# Vorab-Kompression mit unterschiedlichen DPI
a.compress(dpi=100)
b.compress(dpi=200)

# Dateigröße vor Merge
size_a = len(a.current_pdf_data or b"")
size_b = len(b.current_pdf_data or b"")

# Merge mit Preview-Optimierung
a.merge(b, nopreview=True)

# 🔁 Vorschau und ggf. Lazy-Kompression auslösen
a.update_preview()
if not a.current_pdf_data and not a.no_compression:
    a.compress_lazy()

# Hintergrund-Kompression abwarten (max. 2 Sekunden)
for _ in range(20):
    if a.is_compressed and a.current_pdf_data:
        break
    time.sleep(0.1)

# Ergebnisse anzeigen
print("dpi_original:", a.dpi_original)
print("dpi_current:", a.dpi_current)
print("is_compressed:", a.is_compressed)
print("no_compression:", a.no_compression)
print("input_size_a:", size_a)
print("input_size_b:", size_b)
print("merged_current_size:", len(a.current_pdf_data) if a.current_pdf_data else None)

# PDF-Dateien speichern zur Kontrolle
Path("merge_dpi_conflict_a.pdf").write_bytes(a.original_pdf_data or b"")
Path("merge_dpi_conflict_a_compressed.pdf").write_bytes(a._current_pdf_data or b"")
