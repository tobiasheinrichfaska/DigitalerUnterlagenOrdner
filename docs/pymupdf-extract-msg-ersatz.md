# Ersatz für PyMuPDF und extract-msg – Aufwandsanalyse (Stand 2026-11-25)

Keine Rechtsberatung. Grundlage: `docs/licence-audit.md` (beide rot für die Kommerzlizenz). Grep-Inventar im Repo (ohne `.claude/worktrees`), PyPI-JSON (pypi.org/pypi/pypdfium2/json, /olefile/json) und pypdfium2-Doku (pypdfium2.readthedocs.io, Abschnitt Thread safety).

## 1. Inventar `fitz` (PyMuPDF)

**Produktivcode** (nur 5 Dateien):

| Stelle | Fähigkeit |
|---|---|
| `services/render.py:65,132` | Seite(n) rastern (`get_pixmap(dpi)`, PPM→PNG), `capped_dpi(page,…)` braucht Seitengröße |
| `services/render.py:161,174` | `page_count`, `page_dims` (Seitenmaße in pt) |
| `formats/compress_pdf_bytes.py:63,99,119,244` | `page_count` (Truncation-Guards) |
| `formats/compress_pdf_bytes.py:203-241` (`_render_chunk`, `_render_one_page`) | Raster Graustufe/RGB (`csGRAY/csRGB`) pro Seite, in Thread-Pool (je Worker eigenes Dokument) |
| `formats/compress_pdf_bytes.py:267-274` | PDF aus Bildern bauen (`new_page`, `insert_image`, `save`) – ersetzbar durch Pillow/pikepdf/reportlab |
| `formats/pdf_node.py:63` | `page_count` (Fallback pypdf existiert schon) |
| `core/engine.py:207-219` | `split_chunks`: `insert_pdf` Seitenbereich (ersetzbar durch pikepdf/pypdf) |

Text, Annotationen, Formulare: im Produktivcode **nicht** genutzt (PDF-Tool läuft über PDF.js). Der eigentliche Kern ist also: **Rastern + Seitenzahl/-maße**.

**Tests/Skripte:** ca. 25 Testdateien plus `scripts/testkit/samples.py`, `make_*fixtures.py`, `tests/make_fixtures.py` nutzen `fitz` fast nur zum **Erzeugen synthetischer PDFs** (`fitz.open()`, `insert_text/insert_image`) und `page_count`. Speziell: `samples.py` (Widgets/AcroForm, `fitz.Rect`), `test_node_lock.py:110` (`add_freetext_annot`), `test_compress_color_variant.py:36` (`get_pixmap`). Hier ist PyMuPDF als reines **Dev-Werkzeug** unkritisch (wird nicht ausgeliefert), kann aber bleiben, wenn es nur in `requirements-dev.txt` steht. Aufwand für Migration der Tests: nur falls man PyMuPDF auch dev-seitig loswerden will (reportlab/pikepdf, ~2–3 PT).

## 2. Kandidaten

- **pypdfium2 5.15.2** (PyPI, Upload 2026-11-09, also gepflegt): Lizenz laut PyPI „BSD-3-Clause, Apache-2.0, dependency licenses" (PDFium selbst BSD/Apache); `py3-none-win_amd64`-Wheel vorhanden, `py3`-only, d. h. 3.13 kein Problem. Bietet Rastern (`render(scale, grayscale…)`), Seitenzahl, Seitenmaße, Text, `save`, `import_pages`.
- **Thread-Sicherheit (kritisch):** Doku: „PDFium is inherently not thread-safe", auch nicht über verschiedene Dokumente hinweg; Nutzung nur mit globalem Mutex oder Prozessen. Der Render-Cache (`render_service.py`, Thread-Pool, `compress_pdf_bytes` Pool) würde also **serialisiert**: der heutige GIL-bedingte Gewinn (~1,2x laut CLAUDE.md) entfiele, Fairness/Vorrang des Vordergrunds müsste über den Lock neu gebaut werden (ein langer Hintergrund-Render blockiert einen Vordergrund-Render). Alternative Prozess-Pool (deckt sich mit dem bereits notierten, zurückgestellten Multicore-Punkt; braucht `freeze_support`, PyInstaller-Test).
- **pikepdf/pypdf/Pillow** (bereits im Projekt, grün): ersetzen `split_chunks`, Seitenzahl (pikepdf/pypdf, aber pypdf-Parse laut Code-Kommentar langsam), Bild→PDF (Pillow `save(..., "PDF")` oder img2pdf-ähnlich per pikepdf). Rendern können sie nicht.
- Render-Qualität/Geschwindigkeit: PDFium ist als Chrome-Renderer ähnlich schnell wie MuPDF (grobe Einschätzung, **nicht gemessen**; Benchmark nötig). Antialiasing/Graustufen-Pfad unterscheidet sich → Komprimierungs-Bytegrößen und „Lesbarkeit" ändern sich leicht.

## 3. extract-msg

Genutzt wird nur `packages/belegtool-archives/belegtool_archives/archives.py:645-699`: `subject`, `date`, `htmlBody`/`body`/`rtfBody` (Prioritätsliste), `attachments` mit `longFilename`/`shortFilename`/`data`. Content-ID oder Embedded-Message-Sonderlogik gibt es im MSG-Zweig **nicht** (nur bei EML); verschachtelte `.msg`-Anhänge laufen als `data` über `_member_for_attachment` (Verhalten von `att.data` bei Embedded-MSG in extract-msg **ungeprüft**).

Ersatz: `olefile` 0.47 (BSD, rein Python, `py2.py3-none-any`; letzter Upload 2023-12 – stabil, wenig Entwicklung) + eigener Reader (~250–400 Zeilen): Streams `__substg1.0_0037001F` (Betreff), `…1013`/`…1000` (HTML/Text-Body, String8 vs. UTF-16 je nach Typ-Suffix 001E/001F, Codepage aus `__properties_version1.0`), `__attach_version1.0_#NNNNNNNN` mit `3707001F`/`3704001F` (Namen), `37010102` (Daten), `3705`=Attach-Methode (5 = Embedded-MSG, → Unter-Storage als eigenes CFB-Fragment neu serialisieren oder rekursiv lesen), Datum aus `0039/0E06`-Property (FILETIME). **RTF-Body** ist komprimiert (LZFu, MS-OXRTFCP): Dekompression ~60 Zeilen nach Spezifikation, aber HTML-aus-RTF (RTFDE, das LGPL-Teil) wäre nur nötig, wenn weder HTML noch Text-Body da sind; Rückfall „RTF als Datei importieren" ist wie heute (`rtfBody`) möglich. Absicherung: `tests/msg_fixture.py` (143 Zeilen, schreibt echte CFB/MSG-Dateien mit Betreff/Body/Anhängen/Content-ID) deckt Happy Path ab, aber nur selbst erzeugte Dateien → Risiko, Outlook-Eigenheiten (Codepages, Embedded-MSG, Anhang-Methoden, große CFB mit Mini-Stream/DIFAT) zu verfehlen. Dafür 10–20 echte Outlook-Mails (DE, Anhänge, Weiterleitung, HTML/RTF-only) als Golden-Vergleich gegen extract-msg einmalig lokal.

## 4. Optionen und Aufwand (Personentage, grob, ungeprüft)

| Option | Inhalt | Aufwand |
|---|---|---|
| A MSG-Reader mit olefile | Reader + LZFu + Tests + Golden gegen extract-msg | **M** (3–5 PT) |
| B Rendern auf pypdfium2 (Lock) | `render.py`, `_render_one_page`, page_count/dims, Cache-Fairness mit Mutex, Qualitätsvergleich | **M** (4–6 PT) |
| B2 Rendern mit Prozess-Pool | zusätzlich Prozess-Pool, `freeze_support`, PyInstaller-Test | **L** (8–12 PT) |
| C Rest (split_chunks, Bild→PDF, page_count via pikepdf/pdfium) | kleine Ersetzungen | **S** (1–2 PT) |
| D Tests/Skripte entkoppeln | optional | **S–M** |

## 5. Risiken

Thread-Lock in pypdfium2 (Preview-Latenz, Kompressions-Sweep wird seriell), geänderte Rasterergebnisse (Komprimierungsgrößen, „Lesbarkeit geprüft"-Verhalten, Tests mit Größenschwellen), PDFium-Verhalten bei defekten PDFs (sanitize/Load-Integrity-Tests), PyInstaller-Bündelung der PDFium-DLL, Outlook-MSG-Edge-Cases.

## 6. Empfehlung

Machbar, Aufwand insgesamt ca. **2–3 Wochen** (A+B+C, ohne B2). Reihenfolge: (1) **C** zuerst (risikoarm, reduziert die `fitz`-Oberfläche auf Rastern+Maße); (2) **A** (MSG) – kleiner, abgegrenzter Hebel, extract-msg samt RTFDE/LGPL fällt komplett weg; (3) **B** mit Interface `services/render.py` als einziger Rasterungs-Naht, hinter Schalter (Env-Flag) beide Backends parallel betreiben. Qualitätssicherung: Golden-Render-Vergleich PyMuPDF vs. pypdfium2 auf `tests/data/input/` (Seitenzahl/Maße exakt, Pixel-Differenz per SSIM/PSNR-Schwelle, Kompressionsgrößen-Delta protokollieren) und MSG-Golden gegen extract-msg auf echten Mails. B2 nur, falls Messungen zeigen, dass die serielle Variante die Vorschau spürbar verschlechtert. Alternative zum Ersatz von PyMuPDF: Artifex-Kommerzlizenz kaufen (Preis/Bedingungen **nicht recherchiert**).

## 7. Ungeprüft

Reale Render-Performance/-Qualität von pypdfium2 gegenüber PyMuPDF; genaue pdfium-Lizenztexte im Wheel (nur PyPI-Metadaten gelesen); `att.data`-Verhalten bei Embedded-MSG in extract-msg; Pflegezustand von olefile jenseits PyPI-Datum; Windows-Verhalten von PyInstaller mit pdfium; Preise/Konditionen der Artifex-Lizenz.
