import json
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

def test_pdf_split_all():
    files = [f for f in INPUT.glob("*.pdf") if "split" in f.name.lower()]
    assert files, "Keine Dateien mit 'split' im Namen gefunden."

    for file in files:
        node = PDFNode.from_pdf(file.name, file.read_bytes())
        split_nodes = node.split()
        all_nodes = [node] + split_nodes

        for i, n in enumerate(all_nodes, start=1):
            n.no_compression = True
            n.current_pdf_data = None  # explizit auf Original zurücksetzen
            n.dpi_current = None
            n.update_preview()  # Vorschau synchron erzeugen

            # Vorschau muss vorhanden sein
            images = wait_for_real_preview(n)
            assert len(images) == 1, f"Fehlerhafte Vorschau bei {file.stem}_split_{i:02}"

            # Speichern und vergleichen
            name = f"split_{file.stem}_{i:02}"
            pdf_out = OUTPUT / f"{name}.pdf"
            json_out = OUTPUT / f"{name}.json"
            pdf_exp = EXPECTED / f"{name}.pdf"
            json_exp = EXPECTED / f"{name}.json"

            pdf_out.write_bytes(n.current_pdf_data)
            json_out.write_text(json.dumps(n.to_dict(), indent=2, ensure_ascii=False))

            if not pdf_exp.exists() or not json_exp.exists():
                pytest.fail(f"Referenzdaten für {name} fehlen – wurden erzeugt.")
            else:
                assert n.current_pdf_data == pdf_exp.read_bytes(), f"PDF von {name} weicht ab"
                assert n.to_dict() == json.loads(json_exp.read_text()), f"Struktur von {name} weicht ab"
