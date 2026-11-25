# Ersatz für PyMuPDF und extract-msg – Aufwandsanalyse (Stand 2026-11-25)

Keine Rechtsberatung. Grundlage: `docs/licence-audit.md` (beide rot für die Kommerzlizenz). Grep-Inventar im Repo (ohne `.claude/worktrees`), PyPI-JSON (pypi.org/pypi/pypdfium2/json, /olefile/json) und pypdfium2-Doku (pypdfium2.readthedocs.io, Abschnitt Thread safety).

## 0. Status Schritt 1 (C) – erledigt 2026-11-25

Ersetzt durch pikepdf (kein `fitz` mehr dafuer): `split_chunks` (`core/engine.py`), `page_count`/`page_dims` (`belegtool_compress/pdfinfo.py`, `services/render.py` delegiert), `PDFNode._get_pdf_length`, die Seitenzahl-Guards und der Bild→PDF-Aufbau in `belegtool_compress/compress.py` (`_assemble_pdf`). **Verbleibend auf `fitz`: nur Rastern** (`services/render.py` render_page/render_pdf_to_*, `compress.py` `_render_chunk`/`_render_one_page`/`n_pages` fuer das Raster) – plus Test-/Skript-Generatoren.
Paritaet: `tests/test_pdf_nonraster_parity.py` (94 Faelle, fitz als Orakel: /Rotate 90/270/450/-90/45, MediaBox-Offset/invertiert/leer, CropBox, UserUnit, vererbte Attribute, verschluesselt (leeres Passwort), Objekt-/xref-Streams, kaputte xref, 0 Seiten, 300 Seiten) und `packages/belegtool-compress/tests/test_assemble_images.py`/`test_assemble_odd_images.py`. Bewusste Abweichungen: interne GoTo-Links fehlen in Split-Teilen (URI bleibt); PNG-Seiten im Kompressor sind jetzt deflated statt Rohsamples (Variante „png" wird dadurch real klein), 16-bit-Grau-PNG rendert nicht mehr schwarz; 0-Seiten-Dokument wird nie als „kleinere Variante" angeboten.
Messwerte (300 Seiten, 18 MB, alt fitz → neu pikepdf): `page_count` 0,4 → 12 ms (50 Seiten/1 MB: 0,11 → 0,97 ms; 1 Seite: 0,10 → 0,05 ms); `page_dims` 17 → 19 ms; `split_chunks(100)` 103 → 57 ms; `split_chunks(1)` (300 Teile) 2400 → 70 ms; Bildaufbau 300 Seiten JPEG 598 → 176 ms, PNG 1417 → 452 ms.

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

## 8. Weitere Optionen: freie Module, TypeScript, Java (Stand 2026-11-25)

Analyse, kein Code. Belegt = PyPI/npm/Maven-Metadaten bzw. Inhalt der heruntergeladenen Win-x64/cp313-Wheels (unzip -l); „(?)" = nicht geprüft. Aufwand in PT wie in Abschnitt 4. Keine Rechtsberatung.

### A) PyMuPDF-Aufgaben (Rastern, Seitenzahl/-maße, Split/Merge, Bild→PDF)

| Option | Lizenz | Aufwand | Risiko | Urteil |
|---|---|---|---|---|
| pdf.js (Frontend) für die **Vorschau** | Apache-2.0 (npm pdfjs-dist 6.5.438) | M–L (5–8 PT) | mittel | **Ja, für Vorschau – nach RDP-Messung** (s. u.) |
| pypdfium2 5.15.2 für Kompressions-Raster + Maße | BSD-3/Apache-2.0 (Wheel `LICENSES/`); `pdfium.dll` 7,8 MB, Wheel 4,2 MB, `py3-none-win_amd64` | M (4–6 PT) | mittel (Thread-Lock) | **Ja, einziger Python-Raster-Ersatz** |
| pikepdf 10.7.3 / pypdf 6.21.4 für Split/Merge, Seitenzahl | MPL-2.0 / BSD-3, schon im Bundle | S (1–2 PT) | niedrig | **Ja** (kein Rastern nötig) |
| Pillow/reportlab für Bild→PDF | schon im Bundle | S | niedrig | **Ja** |
| pdf-lib (TS) für Split/Merge im Frontend | MIT; Original 1.17.1 zuletzt 2021-11 (tot); Forks `@cantoo/pdf-lib` 2.11.1 (2026-09), `@pdfme/pdf-lib` 6.2.8 (2026-10) | M | mittel (Bytes pendeln über die Bridge; Engine/Undo-Modell liegt in Python) | Nein (Architekturbruch, kein Gewinn ggü. pikepdf) |
| Apache PDFBox 3.0.8 (Java, Sidecar) | Apache-2.0 (Maven Central, 2026-07) | L (10+ PT) | hoch | **Nein** (s. u.) |
| MuPDF/PyMuPDF behalten + Artifex-Kommerzlizenz | Preis nicht öffentlich: „Anfrage" (artifex.com/licensing: „crafted based on your individual use case"); nur Nebenprodukte mit Preis (WebViewer 299 $/Monat, App Kits ab 749 $/Plattform) | S Technik, Vertrag offen | Kosten/Bindung | Fallback, falls Ersatz scheitert |

**(1) pdf.js statt serverseitiger Vorschau.** Fakten: pdf.js ist im Repo nur im PDF-Tool-Entry gebündelt (`webui/src/pdftool/main.js`), nicht im Organizer; die Vorschau holt heute PNGs über `window.pywebview.api.render_window`. Was entfiele: PNG-Encoding + Bridge-Transport, der Vorschau-Pfad von `services/render.py`, Cache-/Fairness-Logik von `render_service.py` (200-MiB-LRU, CPU-Sampler, Prefetch-Pool). Python lieferte nur noch **effektive Bytes** je Knotenversion (crc32 bleibt als Version); pdf.js hält Dokument + Seiten selbst. Zoom-Verankerung (`lib/zoomAnchor.js`, `Preview.jsx`) bleibt logisch erhalten (Seitenindex + Fraktion), Seitenhöhen kommen aus `getViewport` statt `page_dims`; Virtualisierung muss an den Canvas-Lebenszyklus (Render abbrechen, `cleanup`) neu angeschlossen werden. Vorteile: ein Renderer für Vorschau und PDF-Tool, Rasterung im pdf.js-Worker statt GIL-gebunden. Risiken: (a) **Terminal-Server/RDP**: WebView2 läuft dort laut CLAUDE.md bereits im Software-Rendering; pdf.js-Canvas-Rastern ist dann CPU-bound, ob schneller/langsamer als PyMuPDF-Threads unter Last ist **nicht gemessen**; die vorhandene CPU-Fairness (below-normal Threads) greift für Browser-Worker nicht; RAM je Sitzung (?); (b) fremde PDFs laufen im WebView (CSP schon streng; pdfjs-dist 6.5.438 schloss laut Audit eine JS-Ausführungslücke); (c) JBIG2/JPEG2000-Assets (wasm/cmaps) müssten in den Organizer-Entry; (d) Varianten-Vorschau muss denselben Weg nehmen; Vorschau-Engine ≠ Kompressions-Engine, d. h. nicht pixelgleich. **Kompression** rastert weiter serverseitig (pypdfium2); ein pdf.js-Hintergrundworker/Webview dafür ist **nicht empfohlen** (Seiten als PNG zurückpendeln, kein Backpressure, schwer headless testbar).

**(2) pypdfium2.** PyPI: 5.15.2 (2026-11-09), BSD-3/Apache-2.0, Win-x64-Wheel ohne cp-Bindung (3.13 ok). Doku (pypdfium2.readthedocs.io, Thread safety): PDFium ist nicht thread-sicher, auch nicht über verschiedene Dokumente; Lösung = globaler Mutex oder Prozesse. Folge: Kompressions-Pool (`_render_chunk`) wird seriell oder braucht Prozess-Pool (= B2 in §4, `freeze_support`, PyInstaller-Test). Mit pdf.js-Vorschau entfällt die Vorschau-Latenz durch den Lock. Bundle: `pdfium.dll` 7,8 MB (PyMuPDF-Vergleichsgröße nicht gemessen (?)); Variantengrößen ändern sich leicht.

**(4) Java/PDFBox.** Rendern/Split/Merge möglich (Apache-2.0, aktuell), aber: JRE-Sidecar (jlink-Mini-JRE grob 40–60 MB (?)), JVM-Start ~0,3–1 s (?), eigener IPC-Kanal neben `core/ipc`, pro Terminal-Server-Nutzer ein JVM-Prozess (RAM, Fairness-Primitive greifen nicht), zwei Laufzeiten im MSIX. Würde sich nur lohnen, wenn Java ohnehin für `.msg` (POI) käme – tut es nicht. **Urteil: nein.**

### B) `.msg`-Leser (extract-msg GPLv3 + RTFDE LGPL)

| Option | Lizenz / Stand | Aufwand | Risiko | Urteil |
|---|---|---|---|---|
| **olefile-Eigenbau** + `compressed-rtf` | olefile BSD (0.47, 2023-12), compressed-rtf 1.0.7 MIT (2025-03) | M (3–5 PT) | mittel (Outlook-Eigenheiten; Golden-Test nötig) | **Empfohlen** |
| `msg-parser` 1.2.0 | BSD, letzter Release **2019-12**, nur olefile | S–M | mittel-hoch (unmaintained; Embedded-MSG/Codepages (?)) | Nur Vergleichsbasis |
| TS `@kenjiuno/msgreader` 1.29.0 | **Apache-2.0** (npm), Release 2026-10, aktiv | M | mittel | Technisch gut, aber Import-Pipeline (Archiv-Member, Rekursion, Budget) liegt in Python → Bridge-Rückweg nötig. Nein |
| Java Apache POI 6.0.0 (HSMF) | Apache-2.0 (Maven, 2026-10) | L | hoch | Nein (JRE-Gewicht wie A.4) |
| extract-msg behalten | GPLv3 + LGPL | – | Kommerzlizenz rot | Nur AGPL-Variante |

RTF-Body: `compressed-rtf` (MIT) dekomprimiert LZFu fertig. HTML-aus-RTF bräuchte RTFDE (LGPL) – Rückfall: HTML-Body, sonst Text-Body, sonst RTF als Datei. Schwerpunkt der Tests: Embedded-MSG (Methode 5), Codepages, Mini-Stream/große CFB.

### C) HEIC: pillow-heif/libx265

Belegt (Wheel-Inhalt, Win-x64 cp313): **pillow-heif 1.9.0** enthält `libx265-217-….dll` (22,7 MB), `LICENSES_bundled.txt`: Wheel „GPLv2" (gepinnt ist 1.3.0, laut Audit gleiche Struktur). **pi-heif 1.4.0** (PyPI, 2026-06-10, `cp313-win_amd64`, Python-Code BSD-3): enthält nur `libheif`, `libde265` + MinGW-Runtime, **keine x265-DLL**; `LICENSES_bundled.txt`: „binary wheels: LGPLv3". Gleicher Code, anderer Importname (`pi_heif.register_heif_opener()`), kein Encoder (App liest nur), Wheel 2,4 statt 6,6 MB. **Aufwand S (<1 PT)**: `requirements.txt`, `universal_importer/converters.py:18`, `scripts/testkit/samples.py:281` (dort ggf. pillow-heif dev-seitig behalten, falls HEIC erzeugt wird). Restauflage: LGPLv3 (libheif/libde265) bleibt wie svglib/bidi.
Alternativen: x265-DLL aus pillow-heif streichen – ob libheif sie beim Laden hart braucht, **nicht belegt** (?), pi-heif ist die saubere Variante. `imagecodecs` 2026.11.11 (BSD-3, Win-Wheel 19 MB): `_heif.pyd` ohne libheif-/de265-/x265-DLL oder -Lizenz im Wheel (`LICENSE-heif` leer) → HEVC-Decode vermutlich nicht enthalten (?), unbrauchbar ohne Test. WebView2-Decoder: Edge dekodiert HEIC nur mit installierter Windows-HEVC-Erweiterung (?) – nicht verlässlich. **Urteil: pi-heif.**

### D) LGPL-Teile (svglib, python-bidi)

Laut Audit nur über `xhtml2pdf` (Apache-2.0) im Bundle; svglib 2.4.0 ist LGPL-3.0-or-later (PyPI). Eine harmlose Ersetzung innerhalb von xhtml2pdf ist **nicht geprüft**; Umgehen hieße HTML/E-Mail-Import auf einen anderen Renderer umstellen (Edge-Headless-Print als Laufzeitweg ungeprüft). Empfehlung: belassen, als austauschbare Dateien im onedir + Quelltext-Hinweis (Audit §8).

### Empfehlung und Reihenfolge

1. **C: pillow-heif → pi-heif** (S; entfernt GPL-x265, kein Funktionsverlust beim Lesen).
2. **B: olefile-Eigenbau + compressed-rtf** (M); extract-msg samt RTFDE streichen.
3. **A, Teil 1**: split/merge/Bild→PDF/page_count auf pikepdf/pypdf/Pillow (S).
4. **A, Teil 2**: pypdfium2 hinter der Naht `services/render.py` für Kompression + Maße (Vorschau zunächst ebenfalls dort, mit Lock); pdf.js-Vorschau als optionaler Folgeschritt **nur nach RDP-Messung**. Java, pdf-lib, msgreader: nein. Artifex-Lizenz als Rückfall (Angebot: „Anfrage").

### Ungeprüft / zu messen

pdf.js-Vorschau unter RDP/Software-Rendering (Latenz, CPU, RAM je Sitzung) vs. PyMuPDF; pypdfium2 vs. PyMuPDF (Qualität, Zeit, Variantengrößen); x265 „or later" (Audit); pi-heif mit echten iPhone-HEICs unter 3.13/PyInstaller (nur Wheel-Inhalt belegt, kein Lauf); imagecodecs-HEVC; JRE-Größe/Startzeit (Schätzung); Embedded-MSG: extract-msg vs. Eigenbau; olefile-Pflege über PyPI-Datum hinaus; xhtml2pdf-Alternativen; Artifex-Preis; PyInstaller mit `pdfium.dll`.

Quellen: pypi.org/pypi/{pypdfium2,pi-heif,pillow-heif,imagecodecs,msg-parser,compressed-rtf,svglib}/json; registry.npmjs.org/{@kenjiuno/msgreader,pdf-lib,@cantoo/pdf-lib,@pdfme/pdf-lib,pdfjs-dist}; repo1.maven.org (pdfbox, poi-scratchpad maven-metadata.xml); pypdfium2.readthedocs.io (Python API, Thread safety); artifex.com/licensing; webviewer.mupdf.com/pricing; Wheel-Inhalte lokal geprüft.
