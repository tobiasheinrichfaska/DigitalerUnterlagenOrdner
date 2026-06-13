"""Shared constants for the golden Office/ODF round-trip fixtures.

Import-light (no heavy deps) so both the generator (``make_office_fixtures.py``)
and the test (``test_office_golden.py``) can agree on the filenames + sentinels
without pulling in python-docx/openpyxl/python-pptx/odfpy.
"""
from pathlib import Path

INPUT_DIR = Path(__file__).resolve().parent / "data" / "input"

# filename -> a WHITESPACE-FREE sentinel token embedded in the document. The golden
# test asserts the token survives the COM conversion into the rendered PDF text.
# Whitespace-free on purpose: PDF text-extraction can insert/drop spaces, so the
# test matches against the extracted text with all whitespace removed.
SENTINELS = {
    "golden_word.docx":  "BelegtoolGoldenWord2026",
    "golden_excel.xlsx": "BelegtoolGoldenExcel2026",
    "golden_ppt.pptx":   "BelegtoolGoldenPpt2026",
    "golden_text.odt":   "BelegtoolGoldenOdt2026",
    "golden_sheet.ods":  "BelegtoolGoldenOds2026",
    "golden_pres.odp":   "BelegtoolGoldenOdp2026",
}
