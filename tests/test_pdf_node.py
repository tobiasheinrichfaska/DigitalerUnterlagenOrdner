import io
import re
import json
import pytest
from pathlib import Path
from pdf_node import PDFNode
from pypdf import PdfWriter


BASE = Path(__file__).parent / "data"
INPUT = BASE / "input"
EXPECTED = BASE / "expected"
OUTPUT = BASE / "output"

EXPECTED.mkdir(parents=True, exist_ok=True)
OUTPUT.mkdir(parents=True, exist_ok=True)


def get_input_files():
    return sorted(INPUT.glob("*.pdf"))


def write_file(path: Path, data: bytes | dict):
    if isinstance(data, dict):
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_bytes(data)


def read_expected(name: str) -> tuple[bytes | None, dict | None]:
    pdf_path = EXPECTED / f"{name}.pdf"
    json_path = EXPECTED / f"{name}.json"
    pdf_data = pdf_path.read_bytes() if pdf_path.exists() else None
    json_data = json.loads(json_path.read_text()) if json_path.exists() else None
    return pdf_data, json_data


def assert_or_store_expected(name: str, pdf: bytes, structure: dict):
    pdf_out = OUTPUT / f"{name}.pdf"
    json_out = OUTPUT / f"{name}.json"
    write_file(pdf_out, pdf)
    write_file(json_out, structure)

    expected_pdf, expected_json = read_expected(name)

    if expected_pdf is None or expected_json is None:
        write_file(EXPECTED / f"{name}.pdf", pdf)
        write_file(EXPECTED / f"{name}.json", structure)
        pytest.fail(f"Referenzdaten für {name} fehlen – wurden erzeugt. Bitte prüfen.")
    else:
        assert pdf == expected_pdf, f"PDF für {name} weicht ab"
        assert structure == expected_json, f"Struktur für {name} weicht ab"




