# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich
"""Sample files for the manual tests: a catalog of file name → description + builder.

Every file is synthetic (invented names and numbers — no personal data) and built from
code, so the kit can be regenerated at any time. A test case lists the names it needs in
its ``**Beispieldateien:**`` line; adding a sample means adding one catalog row here.

Two properties the tests rely on, both guarded by tests/test_testkit_samples.py:
- text PDFs are "settled": the app finds nothing smaller, so they end up without a
  red "Komprimierung noch nicht entschieden" dot;
- the colour scan is compressible: the app offers smaller variants for it.
"""

import hashlib
import io
import os
import random
import re
import tarfile
import zipfile
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Sequence, Tuple

import fitz
import pikepdf
from PIL import Image, ImageDraw, ImageFont

from universal_importer.archives import _ARCHIVE_MAX_DEPTH

ROOT = Path(__file__).resolve().parents[2]
OFFICE_FIXTURES = ROOT / "tests" / "data" / "input"

A4_W, A4_H = 595, 842
SCAN_PX = (1240, 1754)  # A4 at 150 dpi
FIXED_TIME = (2025, 1, 15, 12, 0, 0)
FIXED_EPOCH = 1736942400  # 2025-01-15 12:00 UTC
COMPANY = "Beispiel GmbH · Musterstraße 1 · 12345 Musterstadt"
INK = (0.12, 0.2, 0.36)

STATUS_DONE, STATUS_TODO, STATUS_PRIOR = "erfasst", "zu erfassen", "vorjahreswert"


@dataclass(frozen=True)
class Sample:
    name: str
    description: str  # German, printed in the test PDF
    build: Callable[[], bytes]


# --- PDF building blocks -----------------------------------------------------------

def _pdf_bytes(doc) -> bytes:
    data = doc.tobytes(deflate=True, garbage=3, no_new_id=True)
    doc.close()
    return data


def _settle(data: bytes) -> bytes:
    """Recompress structurally (same options as the app's "Struktur" method) until
    nothing shrinks, so the app's own pass over the sample finds no smaller variant."""
    while True:
        out = io.BytesIO()
        with pikepdf.open(io.BytesIO(data)) as pdf:
            pdf.save(out, compress_streams=True, recompress_flate=True, deterministic_id=True)
        if len(out.getvalue()) >= len(data):
            return data
        data = out.getvalue()


def _number(seed: str, modulo: int) -> int:
    return int(hashlib.sha1(seed.encode()).hexdigest()[:8], 16) % modulo


def _amount(seed: str) -> str:
    cents = 500 + _number(seed, 95000)
    return f"{cents // 100:4d},{cents % 100:02d} EUR"


def _receipt_lines(label: str, page: int, rows: int = 14) -> Sequence[str]:
    lines = [COMPANY, "", f"Beleg: {label}", f"Belegnummer: 2025-{_number(label, 90000) + 10000}", ""]
    lines += [f"Pos. {row:02d}   Leistung {_number(f'{label}{page}{row}', 900) + 100}   "
              f"{_amount(f'{label}{page}{row}')}" for row in range(1, rows + 1)]
    return lines + ["", f"Summe Seite {page}: {_amount(f'{label}{page}')}"]


@lru_cache(maxsize=None)
def _text_pdf(title: str, pages: Tuple[Tuple[str, ...], ...]) -> bytes:
    doc = fitz.open()
    for number, lines in enumerate(pages, 1):
        page = doc.new_page(width=A4_W, height=A4_H)
        page.insert_text((60, 84), title, fontsize=18, fontname="hebo", color=INK)
        page.draw_line((60, 96), (535, 96), color=INK, width=1.2)
        for row, line in enumerate(lines):
            page.insert_text((60, 128 + 18 * row), line, fontsize=11, fontname="cour")
        page.insert_text((60, 806), "Frei erfundene Beispieldaten - BelegTool-Testkit",
                         fontsize=8, fontname="helv", color=(0.45, 0.45, 0.45))
        page.insert_text((470, 806), f"Seite {number} von {len(pages)}", fontsize=9, fontname="helv")
    return _settle(_pdf_bytes(doc))


def _receipt_pdf(label: str, pages: int) -> bytes:
    return _text_pdf(label, tuple(tuple(_receipt_lines(label, p)) for p in range(1, pages + 1)))


def _link_pdf(label: str, url: str) -> bytes:
    """One receipt page carrying a visible, clickable EXTERNAL link (MT-54: the
    PDF-Tool must open it in the system browser, never in the app window)."""
    doc = fitz.open(stream=_receipt_pdf(label, 1), filetype="pdf")
    page = doc[0]
    rect = fitz.Rect(72, 700, 400, 724)
    page.insert_text((72, 718), f"Mehr dazu: {url}", fontsize=12, color=(0, 0, 0.8))
    page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": url})
    return _pdf_bytes(doc)  # deterministic save (no fresh /ID) — samples must be reproducible


def _numbered_pdf(title: str, pages: int, per_page: int = 34) -> bytes:
    """Numbered lines — a tester can remember "Zeile 141" and check it stays put."""
    return _text_pdf(title, tuple(
        tuple(f"Zeile {(p - 1) * per_page + row:03d}   Buchung {_amount(f'{title}{p}{row}')}"
              for row in range(1, per_page + 1))
        for p in range(1, pages + 1)))


def _form_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=A4_W, height=A4_H)
    page.insert_text((60, 84), "Antrag auf Erstattung (Testformular)", fontsize=18, fontname="hebo", color=INK)
    page.insert_text((60, 112), "Ausfüllbares PDF-Formular für den PDF-Tool-Test.", fontsize=10, fontname="helv")
    fields = (("Name", "Name"), ("Strasse", "Straße"), ("PLZ_Ort", "PLZ / Ort"),
              ("Betrag_EUR", "Betrag (EUR)"), ("Datum", "Datum"))
    for row, (name, label) in enumerate(fields):
        y = 150 + 40 * row
        page.insert_text((60, y + 15), label, fontsize=11, fontname="helv")
        widget = fitz.Widget()
        widget.field_name = name
        widget.field_label = label
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.rect = fitz.Rect(200, y, 520, y + 22)
        widget.text_fontsize = 11
        widget.border_color = (0.3, 0.3, 0.3)
        widget.fill_color = (0.95, 0.97, 1)
        page.add_widget(widget)
    y = 150 + 40 * len(fields)
    page.insert_text((60, y + 13), "Belege liegen bei", fontsize=11, fontname="helv")
    box = fitz.Widget()
    box.field_name = "Belege_liegen_bei"
    box.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    box.rect = fitz.Rect(200, y, 216, y + 16)
    box.border_color = (0.3, 0.3, 0.3)
    box.field_value = False
    page.add_widget(box)
    return _pdf_bytes(doc)


# --- raster ("scanned") material ---------------------------------------------------

def _font(size: int, bold: bool = False):
    for name in ("arialbd.ttf" if bold else "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _paper(size, seed: int, tint=(249, 246, 238)) -> Image.Image:
    """Off-white sheet with soft grain, like a flatbed scan (seeded → reproducible)."""
    small = (size[0] // 3, size[1] // 3)
    grain = Image.frombytes("L", small, random.Random(seed).randbytes(small[0] * small[1]))
    grain = grain.resize(size, Image.BILINEAR)
    return Image.blend(Image.new("RGB", size, tint), Image.merge("RGB", (grain, grain, grain)), 0.03)


def _jpeg(image: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _scan_page(title: str, page: int, total: int) -> Image.Image:
    width, height = SCAN_PX
    img = _paper(SCAN_PX, seed=page)
    draw = ImageDraw.Draw(img)
    draw.rectangle([70, 70, width - 70, 210], fill=(36, 64, 118))
    draw.text((100, 108), title, font=_font(58, bold=True), fill="white")
    draw.ellipse([width - 330, 250, width - 110, 470], outline=(196, 40, 40), width=8)
    draw.text((width - 220, 360), "BEZAHLT", font=_font(36, bold=True), fill=(196, 40, 40), anchor="mm")
    draw.text((100, 270), COMPANY, font=_font(26), fill=(40, 40, 40))
    draw.text((100, 320), f"Rechnung 2025-{4400 + page}   Seite {page} von {total}", font=_font(34, bold=True),
              fill=(20, 20, 20))
    y = 520
    for row in range(1, 19):
        if row % 2:
            draw.rectangle([90, y - 6, width - 90, y + 46], fill=(226, 236, 226))
        draw.text((110, y), f"Pos. {row:02d}", font=_font(28), fill=(15, 15, 15))
        draw.text((260, y), f"Artikel {_number(f'{title}{page}{row}', 9000) + 1000}", font=_font(28), fill=(15, 15, 15))
        draw.text((width - 380, y), _amount(f"{title}{page}{row}"), font=_font(28), fill=(15, 15, 15))
        y += 56
    draw.rectangle([90, y + 20, width - 90, y + 110], fill=(255, 236, 179), outline=(36, 64, 118), width=3)
    draw.text((110, y + 44), f"Summe Seite {page}: {_amount(f'{title}{page}')}", font=_font(34, bold=True),
              fill=(10, 10, 10))
    return img


@lru_cache(maxsize=None)
def _scan_pdf(title: str, pages: int) -> bytes:
    doc = fitz.open()
    for number in range(1, pages + 1):
        page = doc.new_page(width=A4_W, height=A4_H)
        page.insert_image(page.rect, stream=_jpeg(_scan_page(title, number, pages), quality=85))
    return _pdf_bytes(doc)


@lru_cache(maxsize=None)
def _big_pdf(pages: int) -> bytes:
    """Many pages, small file: one letterhead image shared by every page."""
    sheet = _paper(SCAN_PX, seed=120, tint=(244, 247, 252))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle([0, 0, SCAN_PX[0], 150], fill=(36, 64, 118))
    draw.text((90, 46), "Großes Testdokument", font=_font(56, bold=True), fill="white")
    draw.rectangle([0, 150, 46, SCAN_PX[1]], fill=(214, 226, 244))
    letterhead = _jpeg(sheet, quality=82)

    doc = fitz.open()
    xref = 0
    for number in range(1, pages + 1):
        page = doc.new_page(width=A4_W, height=A4_H)
        xref = page.insert_image(page.rect, stream=None if xref else letterhead, xref=xref)
        page.insert_text((60, 150), f"Seite {number}", fontsize=54, fontname="hebo", color=INK)
        page.insert_text((60, 176), f"von {pages} - zum Blättern und Scrollen", fontsize=12, fontname="helv")
        for row in range(1, 25):
            page.insert_text((60, 210 + 22 * row), f"Seite {number:03d} · Zeile {row:02d} · {_amount(f'{number}{row}')}",
                             fontsize=11, fontname="cour")
    return _pdf_bytes(doc)


def _receipt_photo() -> Image.Image:
    table = _paper((1200, 1600), seed=7, tint=(150, 110, 78))
    slip = _paper((560, 1180), seed=8, tint=(252, 252, 248)).convert("RGBA")
    draw = ImageDraw.Draw(slip)
    draw.text((60, 50), "KASSENBON", font=_font(54, bold=True), fill=(20, 20, 20))
    draw.text((60, 130), "Bäckerei Muster", font=_font(34), fill=(20, 20, 20))
    for row in range(1, 13):
        draw.text((60, 200 + row * 62), f"Artikel {row:02d}", font=_font(30), fill=(30, 30, 30))
        draw.text((330, 200 + row * 62), _amount(f"bon{row}")[-10:], font=_font(30), fill=(30, 30, 30))
    draw.text((60, 1040), f"SUMME  {_amount('bon')}", font=_font(40, bold=True), fill=(20, 20, 20))
    slip = slip.rotate(4, expand=True, resample=Image.BICUBIC)
    table.paste(slip, (300, 190), slip)
    return table


def _clean_scan() -> Image.Image:
    img = Image.new("RGB", (900, 1270), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, 860, 1230], outline=(60, 60, 60), width=3)
    draw.text((80, 80), "QUITTUNG", font=_font(64, bold=True), fill=(30, 30, 30))
    draw.text((80, 190), "Nr. 2025-0815", font=_font(36), fill=(30, 30, 30))
    for row, text in enumerate(("Betrag: 84,30 EUR", "für: Büromaterial", "von: Beispiel GmbH",
                                "Ort / Datum: Musterstadt, 15.01.2025")):
        draw.text((80, 320 + row * 90), text, font=_font(38), fill=(20, 20, 20))
        draw.line([80, 372 + row * 90, 820, 372 + row * 90], fill=(120, 120, 120), width=2)
    return img


def _chart() -> Image.Image:
    img = Image.new("RGB", (1000, 700), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "Ausgaben je Quartal (Beispiel)", font=_font(40, bold=True), fill=(30, 30, 30))
    colours = ((36, 64, 118), (60, 140, 90), (220, 150, 40), (196, 40, 40))
    for quarter, colour in enumerate(colours):
        top = 560 - (140 + _number(f"q{quarter}", 320))
        draw.rectangle([140 + quarter * 200, top, 280 + quarter * 200, 560], fill=colour)
        draw.text((180 + quarter * 200, 580), f"Q{quarter + 1}", font=_font(34), fill=(30, 30, 30))
    draw.line([100, 560, 940, 560], fill=(60, 60, 60), width=3)
    return img


def _asset(name: str) -> bytes:
    """Committed binary sample. HEIC is read-only in the app (pi-heif ships no encoder,
    deliberately: no GPL x265), so this one is a fixed asset encoded once from
    ``_receipt_photo().resize((900, 1200))`` with a dev-only HEVC encoder."""
    with open(os.path.join(os.path.dirname(__file__), "assets", name), "rb") as f:
        return f.read()


def _image_bytes(image: Image.Image, fmt: str, **options) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt, **options)
    return buf.getvalue()


# --- containers ---------------------------------------------------------------------

def _zip(members: Dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=FIXED_TIME), data, zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def _tar(members: Dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = FIXED_EPOCH
            archive.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _eml(subject: str, body: str, attachments: Dict[str, Tuple[str, bytes]]) -> bytes:
    """``attachments``: file name → (MIME type, data)."""
    tag = hashlib.sha1(subject.encode()).hexdigest()[:16]
    msg = EmailMessage()
    msg["From"] = "Erika Mustermann <erika.mustermann@example.com>"
    msg["To"] = "Buchhaltung <buchhaltung@example.com>"
    msg["Subject"] = subject
    msg["Date"] = "Wed, 15 Jan 2025 10:30:00 +0100"
    msg["Message-ID"] = f"<{tag}@example.com>"
    msg.set_content(body)
    for name, (mime, data) in attachments.items():
        maintype, subtype = mime.split("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    msg.set_boundary(f"=_belegtool_testkit_{tag}")
    return msg.as_bytes()


# A harmless stand-in for "an EXE renamed to .pdf": only the two signature bytes the
# import gate checks, followed by plain text. Not a valid program — nothing can run it.
FAKE_EXE = b"MZ" + bytes(62) + "Harmlose Testdatei für BelegTool (MT-05) – kein ausführbares Programm.\n".encode()


# Top archive + every level the importer opens + one level it refuses.
TOO_DEEP_LEVELS = _ARCHIVE_MAX_DEPTH + 2


def _nested_zip(levels: int) -> bytes:
    """A zip chain ``levels`` deep with one PDF at the bottom."""
    data = _zip({"beleg_ganz_innen.pdf": _receipt_pdf("Beleg ganz innen", 1)})
    for level in range(levels - 1, 0, -1):
        data = _zip({f"ebene_{level + 1}.zip": data, f"beleg_ebene_{level}.pdf": _receipt_pdf(f"Beleg Ebene {level}", 1)})
    return data


# --- .belegtool documents (declared as data) ------------------------------------------

def _folder(name, *children):
    return {"name": name, "children": children}


def _leaf(name, pages=1, scan=False):
    return {"name": name, "pages": pages, "scan": scan}


# The root's name is not shown anywhere: on open the app titles a document after its file.
BEISPIELMAPPE = _folder(
    "Beispielmappe",
    _folder("01 Eingangsrechnungen",
            _leaf("Telefon_2025-01.pdf"),
            _leaf("Strom_Abschlag_2025-01.pdf"),
            _leaf("Buerobedarf_Quittung.pdf"),
            _leaf("Sammelrechnung_Wartung.pdf", pages=4)),
    _folder("02 Bank",
            _leaf("Kontoauszug_2025-01.pdf", pages=3),
            _leaf("Kontoauszug_2025-02.pdf", pages=2),
            _folder("Darlehen",
                    _leaf("Zinsbescheinigung_2024.pdf"),
                    _leaf("Tilgungsplan.pdf", pages=2))),
    _folder("03 Vorjahr 2024",
            _leaf("Miete_2024-12.pdf"),
            _leaf("Versicherung_2024.pdf")),
    _leaf("Deckblatt.pdf"),
)

STATUSMIX = _folder("04 Statusmix", _leaf("Beleg_gruen.pdf"), _leaf("Beleg_rot.pdf"), _leaf("Beleg_ohne_Status.pdf"))

# 24 documents the app cannot shrink (their red dot clears by itself) next to two it can.
VIELE_KLEINE_BELEGE = _folder(
    "Viele_kleine_Belege",
    _folder("Eingang", *(_leaf(f"Beleg_{n:02d}.pdf") for n in range(1, 13))),
    _folder("Ausgang", *(_leaf(f"Beleg_{n:02d}.pdf") for n in range(13, 25))),
    _folder("Scans", _leaf("Scan_Kassenbon_A.pdf", scan=True), _leaf("Scan_Kassenbon_B.pdf", scan=True)),
)

ZWEITE_MAPPE = _folder(
    "Zweite_Mappe",
    _folder("Beiträge", _leaf("Beitragsliste_2025.pdf", pages=2), _leaf("Mahnung_Muster.pdf")),
    _folder("Veranstaltungen", _leaf("Sommerfest_Abrechnung.pdf", pages=2), _leaf("Hallenmiete.pdf")),
)

STATUS_BY_NAME = {
    "Telefon_2025-01.pdf": STATUS_DONE,
    "Strom_Abschlag_2025-01.pdf": STATUS_DONE,
    "Buerobedarf_Quittung.pdf": STATUS_PRIOR,
    "Sammelrechnung_Wartung.pdf": STATUS_TODO,
    "Beleg_gruen.pdf": STATUS_DONE,
    "Beleg_rot.pdf": STATUS_PRIOR,
}
TAGS_BY_NAME = {
    "02 Bank": ("Bank",),
    "Telefon_2025-01.pdf": ("Telefon", "Betriebsausgabe"),
    "Strom_Abschlag_2025-01.pdf": ("Energie", "Betriebsausgabe"),
    "Miete_2024-12.pdf": ("Miete",),
    "Versicherung_2024.pdf": ("Versicherung",),
    "Zinsbescheinigung_2024.pdf": ("Steuer",),
}


def _with_child(tree, child):
    return {**tree, "children": (*tree["children"], child)}


def _node(sample: str, spec, statuses, tags, path=""):
    from core.model import Node
    name = spec["name"]
    here = f"{path}/{name}"
    common = dict(name=name, id=hashlib.sha1(f"{sample}{here}".encode()).hexdigest()[:32],
                  tags=tuple(tags.get(name, ())))
    if "children" in spec:
        return Node(is_folder=True, **common,
                    children=tuple(_node(sample, child, statuses, tags, here) for child in spec["children"]))
    pages, title = spec["pages"], name.removesuffix(".pdf")
    data = _scan_pdf(title, pages) if spec["scan"] else _receipt_pdf(title, pages)
    return Node(pdf_length=pages, original_data=data, status=statuses.get(name, ""), **common)


_PDF_ID = re.compile(rb"/ID \[<[0-9a-f]{32}><[0-9a-f]{32}>\]")


def _stable_id(data: bytes) -> bytes:
    """The app's writer stamps a time-based /ID. Swap it for one derived from the content
    (same length, so every offset still holds) to keep the samples reproducible."""
    digest = hashlib.sha1(_PDF_ID.sub(b"", data)).hexdigest()[:32].encode()
    return _PDF_ID.sub(b"/ID [<" + digest + b"><" + digest + b">]", data)


def _belegtool(sample: str, tree, statuses=None, tags=None) -> bytes:
    from core.bridge import document_to_storage
    from core.model import Document
    root = _node(sample, tree, statuses or {}, tags or {})
    return _stable_id(document_to_storage(Document(root)).to_bytes())


def _corrupt_belegtool() -> bytes:
    """Deterministically damaged .belegtool for MT-15d: a same-length byte patch makes
    the embedded structure claim far more pages than the file holds, so the load
    degrades reliably ('gekürzt'/'übersprungen' warnings, path not bound) — unlike
    hand-made random corruption, which only sometimes hits a vital byte."""
    data = _belegtool("Defekt", _folder("Defekte_Mappe",
                                        _leaf("Beleg_A.pdf"), _leaf("Beleg_B.pdf")))
    patched = data.replace(b'"pdf_length": 1', b'"pdf_length": 7', 1)
    if patched == data:
        raise AssertionError("pdf_length marker not found — the sample would be healthy")
    return patched


# --- the catalog ----------------------------------------------------------------------

def _office(name: str) -> Callable[[], bytes]:
    return lambda: (OFFICE_FIXTURES / name).read_bytes()


_CATALOG = (
    Sample("Rechnung_5_Seiten.pdf", "Text-PDF mit 5 Seiten (Rechnung mit Positionen).",
           lambda: _receipt_pdf("Rechnung Muster-Telefon AG", 5)),
    Sample("Kontoauszug_8_Seiten.pdf", "Text-PDF mit 8 Seiten und durchnummerierten Zeilen (zum Wiederfinden einer Stelle).",
           lambda: _numbered_pdf("Kontoauszug 2025", 8)),
    Sample("Dokument_3_Seiten.pdf", "Text-PDF mit 3 Seiten – zum Splitten.",
           lambda: _receipt_pdf("Dokument zum Splitten", 3)),
    Sample("Teil_A_1_Seite.pdf", "Text-PDF mit 1 Seite – erster Teil zum Zusammenführen.",
           lambda: _receipt_pdf("Teil A", 1)),
    Sample("Teil_B_2_Seiten.pdf", "Text-PDF mit 2 Seiten – zweiter Teil zum Zusammenführen.",
           lambda: _receipt_pdf("Teil B", 2)),
    Sample("Formular_Antrag.pdf", "Ausfüllbares PDF-Formular (5 Textfelder, 1 Kontrollkästchen).", _form_pdf),
    Sample("Rechnung_mit_Link.pdf", "Rechnung mit einem anklickbaren Internet-Link (für den Browser-Test im PDF-Tool).",
           lambda: _link_pdf("Rechnung mit Link", "https://example.com/")),
    Sample("ZZZ_TEST_Dokument.pdf", "Deutlich als Test markiertes PDF (1 Seite) für die DATEV-Ablage.",
           lambda: _receipt_pdf("ZZZ TEST - nicht produktiv", 1)),
    Sample("Farbscan_Rechnung_3_Seiten.pdf", "Farbiger „Scan“ mit 3 Seiten – lässt sich deutlich komprimieren.",
           lambda: _scan_pdf("Farbscan Rechnung", 3)),
    Sample("Farbscan_Rechnung_6_Seiten.pdf", "Farbiger „Scan“ mit 6 Seiten – wird erst auf Anforderung berechnet (mehr als 5 Seiten).",
           lambda: _scan_pdf("Farbscan Rechnung lang", 6)),
    Sample("Grosses_Dokument_120_Seiten.pdf", "PDF mit 120 Seiten – für Vorschau, Cache und lange Berechnungen.",
           lambda: _big_pdf(120)),
    Sample("Foto_Kassenbon.jpg", "Foto eines Kassenbons (JPG).",
           lambda: _jpeg(_receipt_photo(), quality=85)),
    Sample("Scan_Quittung.png", "Gescannte Quittung (PNG).",
           lambda: _image_bytes(_clean_scan(), "PNG", optimize=True)),
    Sample("Grafik_Diagramm.webp", "Diagramm als WEBP-Bild.",
           lambda: _image_bytes(_chart(), "WEBP", quality=85)),
    Sample("Handyfoto_Beleg.heic", "Handyfoto im HEIC-Format (iPhone-Standard).",
           lambda: _asset("Handyfoto_Beleg.heic")),
    Sample("Scan_Kontoblatt.bmp", "Gescanntes Blatt als BMP-Bild.",
           lambda: _image_bytes(_clean_scan().convert("L").resize((600, 847)), "BMP")),
    Sample("Scan_Vertrag.tif", "Gescanntes Blatt als TIFF-Bild (eine Seite).",
           lambda: _image_bytes(_clean_scan(), "TIFF", compression="tiff_lzw")),
    Sample("Mail_mit_Anhaengen.eml", "E-Mail mit drei Anhängen: ein PDF, ein Foto und eine nicht unterstützte Datei.",
           lambda: _eml("Belege Januar 2025", "Guten Tag,\n\nanbei die Belege für Januar.\n\nViele Grüße\nErika Mustermann\n", {
               "Rechnung_Januar.pdf": ("application/pdf", _receipt_pdf("Rechnung Januar", 2)),
               "Foto_Kassenbon.jpg": ("image/jpeg", _jpeg(_receipt_photo(), quality=85)),
               "Messwerte.xyz": ("application/octet-stream", b"Unbekanntes Format - laesst sich nicht umwandeln.\n"),
           })),
    Sample("Belege_mit_Unterordnern.zip", "ZIP-Archiv mit Unterordnern; zwei Dateien heißen gleich (beleg.pdf).",
           lambda: _zip({
               "rechnungen/2024/beleg.pdf": _receipt_pdf("Beleg 2024", 1),
               "rechnungen/2024/kassenbon.jpg": _jpeg(_receipt_photo(), quality=85),
               "rechnungen/2023/beleg.pdf": _receipt_pdf("Beleg 2023", 2),
               "vertraege/mietvertrag.pdf": _receipt_pdf("Mietvertrag", 3),
           })),
    Sample("Belege_Archiv.tar", "TAR-Archiv mit Unterordnern.",
           lambda: _tar({
               "bank/2025/kontoauszug.pdf": _receipt_pdf("Kontoauszug TAR", 2),
               "bank/2024/kontoauszug.pdf": _receipt_pdf("Kontoauszug TAR Vorjahr", 1),
           })),
    Sample("getarnte_EXE_rechnung.pdf", "Harmlose Attrappe: beginnt wie ein Windows-Programm, heißt aber .pdf. Kein echtes Programm.",
           lambda: FAKE_EXE),
    Sample("Mail_mit_getarnter_EXE.eml", "E-Mail, deren Anhang „rechnung.pdf“ dieselbe harmlose Attrappe ist.",
           lambda: _eml("Ihre Rechnung", "Guten Tag,\n\nim Anhang Ihre Rechnung.\n", {
               "rechnung.pdf": ("application/pdf", FAKE_EXE),
               "echte_Rechnung.pdf": ("application/pdf", _receipt_pdf("Echte Rechnung", 1)),
           })),
    Sample("Verschachtelt_ZIP_in_ZIP.zip", "ZIP, das ein weiteres ZIP enthält (darin ein PDF).",
           lambda: _nested_zip(2)),
    Sample("Mail_mit_ZIP_Anhang.eml", "E-Mail mit einem ZIP als Anhang (darin ein PDF).",
           lambda: _eml("Unterlagen als ZIP", "Guten Tag,\n\ndie Unterlagen liegen als ZIP bei.\n", {
               "unterlagen.zip": ("application/zip", _zip({"beleg_im_zip.pdf": _receipt_pdf("Beleg im ZIP", 1)})),
           })),
    Sample("Zu_tief_verschachtelt.zip",
           f"{TOO_DEEP_LEVELS} ineinander verpackte ZIPs – die innerste Ebene ist zu tief.",
           lambda: _nested_zip(TOO_DEEP_LEVELS)),
    Sample("Notiz.txt", "Reine Textdatei.",
           lambda: "Notiz zum Beleg\n\nBitte bis zum 31.01.2025 erfassen.\nFrei erfundene Beispieldaten.\n".encode()),
    Sample("Liesmich.md", "Markdown-Textdatei.",
           lambda: "# Hinweise zur Ablage\n\nBelege bitte *monatlich* einreichen.\n\n- Rechnungen\n- Kontoauszüge\n".encode()),
    Sample("Bestellbestaetigung.html", "HTML-Seite mit Überschrift und Absatz.",
           lambda: ("<html><body><h1>Bestellbestätigung</h1><p>Vielen Dank für Ihre Bestellung Nr. 4711 "
                    "bei der Beispiel GmbH.</p></body></html>").encode()),
    Sample("Unbekanntes_Format.xyz", "Datei mit einer Endung, die BelegTool nicht kennt.",
           lambda: b"Unbekanntes Format - laesst sich nicht umwandeln.\n"),
    Sample("Brief.docx", "Word-Dokument (enthält den Text „BelegtoolGoldenWord2026“).", _office("golden_word.docx")),
    Sample("Tabelle.xlsx", "Excel-Tabelle (enthält „BelegtoolGoldenExcel2026“).", _office("golden_excel.xlsx")),
    Sample("Praesentation.pptx", "PowerPoint-Präsentation (enthält „BelegtoolGoldenPpt2026“).", _office("golden_ppt.pptx")),
    Sample("Text.odt", "OpenDocument-Text (enthält „BelegtoolGoldenOdt2026“).", _office("golden_text.odt")),
    Sample("Tabelle.ods", "OpenDocument-Tabelle (enthält „BelegtoolGoldenOds2026“).", _office("golden_sheet.ods")),
    Sample("Folien.odp", "OpenDocument-Präsentation (enthält „BelegtoolGoldenOdp2026“).", _office("golden_pres.odp")),
    Sample("Beispielmappe.belegtool", "BelegTool-Dokument: 3 Ordner (einer mit Unterordner), 11 Belege, einige mehrseitig.",
           lambda: _belegtool("Beispielmappe", BEISPIELMAPPE)),
    Sample("Beispielmappe_mit_Status.belegtool", "Wie die Beispielmappe, mit gesetzten Status und dem Ordner „04 Statusmix“.",
           lambda: _belegtool("Status", _with_child(BEISPIELMAPPE, STATUSMIX), statuses=STATUS_BY_NAME)),
    Sample("Beispielmappe_mit_Tags.belegtool", "Wie die Beispielmappe, mit Tags an einem Ordner und fünf Dokumenten.",
           lambda: _belegtool("Tags", BEISPIELMAPPE, tags=TAGS_BY_NAME)),
    Sample("Viele_kleine_Belege.belegtool", "BelegTool-Dokument: 24 einseitige Text-Belege (nicht verkleinerbar) und 2 Scans (verkleinerbar).",
           lambda: _belegtool("Viele", VIELE_KLEINE_BELEGE)),
    Sample("Zweite_Mappe.belegtool", "Ein zweites, anderes BelegTool-Dokument (für das zweite Fenster).",
           lambda: _belegtool("Zweite", ZWEITE_MAPPE)),
    Sample("Defekte_Mappe.belegtool", "ABSICHTLICH beschädigtes BelegTool-Dokument (Struktur behauptet mehr Seiten als vorhanden) — für MT-15d; öffnet mit Warnung, Speichern wird zu Speichern-unter.",
           _corrupt_belegtool),
)

SAMPLES: Dict[str, Sample] = {sample.name: sample for sample in _CATALOG}
