import json
import re
import pytest
from pathlib import Path
from pdf_node import PDFNode
from helpers import create_valid_pdf

BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


import json
import re
import pytest
import io
from pathlib import Path
from pdf_node import PDFNode
from helpers import create_valid_pdf

from pypdf import PdfReader  # Optional für Textvergleich (siehe unten)

BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


import json
import re
import pytest
from pathlib import Path
from pdf_node import PDFNode

BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


def test_pdf_merge_groups():
    groups = {}
    for file in INPUT.glob("*.pdf"):
        match = re.search(r"merge(\d+)", file.stem.lower())
        if match:
            gid = match.group(1)
            groups.setdefault(gid, []).append(file)

    assert groups, "Keine Dateien mit 'merge<ID>' gefunden."

    for gid, files in groups.items():
        nodes = []

        for f in sorted(files):
            data = f.read_bytes()

            # Sichere Initialisierung ohne Nebenwirkungen
            node = PDFNode(name=f.name, pdf_data=None)
            node.no_compression = True
            node.set_original_and_current_data(
                original_data=data,
                current_data=None,
                dpi_original=None,
                dpi_current=None,
                no_compression=True
            )

            nodes.append(node)

        base = nodes[0]
        for other in nodes[1:]:
            base.merge(other, nopreview=True)

        result_pdf = base.current_pdf_data
        result_json = base.to_dict()

        name = f"merge{gid}"
        pdf_out = OUTPUT / f"{name}.pdf"
        json_out = OUTPUT / f"{name}.json"
        pdf_exp = EXPECTED / f"{name}.pdf"
        json_exp = EXPECTED / f"{name}.json"

        pdf_out.write_bytes(result_pdf)
        json_out.write_text(json.dumps(result_json, indent=2, ensure_ascii=False))

        if not pdf_exp.exists() or not json_exp.exists():
            pytest.fail(f"Referenzdaten für {name} fehlen – wurden erzeugt.")
        else:
            expected_pdf_bytes = pdf_exp.read_bytes()
            if result_pdf != expected_pdf_bytes:
                pytest.fail(f"PDF von {name} weicht ab (binär ungleich)")

            expected_json = json.loads(json_exp.read_text())
            assert result_json == expected_json, f"Struktur von {name} weicht ab"

def test_merge_does_not_use_internal_current_pdf_data_directly():
    node1 = PDFNode("n1", pdf_data=create_valid_pdf(pages=1))
    node2 = PDFNode("n2", pdf_data=create_valid_pdf(pages=1))

    try:
        node1.merge(node2, nopreview=True)
    except AttributeError as e:
        pytest.fail(f"Merge verwendet falsches internes Attribut: {e}")
