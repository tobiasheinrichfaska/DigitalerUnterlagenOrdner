"""Build a realistic, NON-personal demo .belegtool for Store screenshots / demos.

    python scripts/make_demo_belegtool.py [out_path]   # default: C:\\tmp\\demo.belegtool

Tree with varied statuses (green/yellow/red/none → status dots) and tags (→ chips), and
generated sample PDFs so the preview pane shows content. Open it with:
    python host.py <out_path>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # noqa: E402

from core.model import (  # noqa: E402
    Document, Node, STATUS_DONE, STATUS_TODO, STATUS_PRIOR_YEAR, STATUS_NONE,
)
from core.bridge import save_belegtool  # noqa: E402


def _pdf(title, lines):
    d = fitz.open()
    p = d.new_page(width=595, height=842)  # A4
    p.insert_text((60, 90), title, fontsize=18)
    p.draw_line(fitz.Point(60, 100), fitz.Point(535, 100))
    y = 130
    for ln in lines:
        p.insert_text((60, y), ln, fontsize=11)
        y += 20
    data = d.tobytes()
    d.close()
    return data


def _leaf(name, title, lines, status=STATUS_NONE, tags=()):
    return Node(name=name, pdf_length=1, original_data=_pdf(title, lines),
                status=status, tags=tuple(tags))


root = Node(name="Steuer 2025", is_folder=True, children=(
    Node(name="Eingangsrechnungen", is_folder=True, children=(
        _leaf("Telekom_2025-01.pdf", "Telekom Deutschland GmbH",
              ["Rechnung Nr. 2025-000123", "Leistung: Mobilfunk Januar 2025",
               "Betrag: 49,99 EUR"], STATUS_DONE, ["Telekom", "Telefon"]),
        _leaf("Stadtwerke_2025-01.pdf", "Stadtwerke Musterstadt",
              ["Abschlag Strom und Gas", "Zeitraum: Januar 2025",
               "Betrag: 120,00 EUR"], STATUS_TODO, ["Energie"]),
        _leaf("Buerobedarf.pdf", "Buerohandel Beispiel AG",
              ["Quittung", "Druckerpapier, Toner", "Betrag: 84,30 EUR"],
              STATUS_NONE, ["Buero"]),
    )),
    Node(name="Vorjahr 2024", is_folder=True, children=(
        _leaf("Miete_2024-12.pdf", "Gewerbemiete (Dauerrechnung)",
              ["Objekt: Musterstrasse 1", "Monat: Dezember 2024",
               "Betrag: 850,00 EUR"], STATUS_PRIOR_YEAR, ["Miete"]),
        _leaf("Versicherung_2024.pdf", "Beispiel Versicherung AG",
              ["Betriebshaftpflicht", "Jahresbeitrag 2024",
               "Betrag: 312,00 EUR"], STATUS_PRIOR_YEAR, ["Versicherung"]),
    )),
    _leaf("Deckblatt.pdf", "Unterlagen 2025 - Uebersicht",
          ["Mandant: Beispiel GmbH", "Zeitraum: 01.01.2025 - 31.12.2025"],
          STATUS_NONE, ()),
))

out = sys.argv[1] if len(sys.argv) > 1 else r"C:\tmp\demo.belegtool"
os.makedirs(os.path.dirname(out), exist_ok=True)
save_belegtool(Document(root), out)
print("wrote", out)
