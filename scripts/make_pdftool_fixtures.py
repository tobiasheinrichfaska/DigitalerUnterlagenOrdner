# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""(Re)build the PDF-Tool e2e fixtures under webui/public/ (committed).

    python scripts/make_pdftool_fixtures.py

spike-link.pdf — one page with an EXTERNAL link annotation. Guards the H2 fix
(audit 2026-11-03): a link in an untrusted PDF must open in the system browser
(target=_blank), never navigate the bridged pywebview window.
"""
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "webui" / "public"


def make_spike_link() -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "SPIKE-LINK-PDF", fontsize=16)
    rect = fitz.Rect(72, 140, 300, 170)
    page.insert_text((72, 160), "EXTERNER-LINK", fontsize=14, color=(0, 0, 1))
    page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": "https://example.com/"})
    doc.save(OUT / "spike-link.pdf", deflate=True)
    doc.close()


def make_radio_form() -> None:
    """Radio group, one selected. PDF.js calls annotationStorage.setValue while rendering radio
    widgets, which used to flag the untouched document as modified (audit R11-2). (reportlab:
    PyMuPDF's radio-widget API produced no usable group.)"""
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(OUT / "spike-radio.pdf"))
    c.drawString(72, 800, "SPIKE-RADIO-PDF")
    form = c.acroForm
    form.radio(name="r", value="a", selected=True, x=50, y=600, size=20)
    form.radio(name="r", value="b", selected=False, x=100, y=600, size=20)
    c.showPage()
    c.save()


if __name__ == "__main__":
    make_spike_link()
    make_radio_form()
    print(f"geschrieben: {OUT / 'spike-link.pdf'}")
    sys.exit(0)
