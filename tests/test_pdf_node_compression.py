import pytest
from pathlib import Path
from pdf_node import PDFNode
from helpers import wait_for_real_preview

BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)

def test_pdf_compression_loop():
    files = [f for f in INPUT.glob("*.pdf") if "compress" in f.name.lower()]
    assert files, "Keine Eingabedateien mit 'compress' im Namen gefunden."

    for file in files:
        node = PDFNode.from_pdf(name=file.name, source=file.read_bytes())

        # Warten auf Abschluss der Vorschau (impliziert: Kompression ist durchgelaufen)
        wait_for_real_preview(node)

        # Zugriff direkt auf _current_pdf_data, kein Fallback!
        result = node._current_pdf_data
        if not result:
            pytest.fail(f"Kompression bei {file.name} schlug fehl oder wurde nicht durchgeführt.")

        output_path = OUTPUT / f"{file.stem}_compressed.pdf"
        output_path.write_bytes(result)

        expected_path = EXPECTED / f"{file.stem}_compressed.pdf"
        if not expected_path.exists():
            pytest.fail(f"Referenz für {file.name} fehlt – wurde erzeugt. Bitte prüfen und übernehmen.")
        else:
            expected = expected_path.read_bytes()
            assert result == expected, f"Kompressionsergebnis von {file.name} weicht ab"
