# Third-Party Notices

DigitalerUnterlagenOrdner (BelegTool) is licensed under AGPL-3.0-or-later (see `LICENSE`, full text in `COPYING`) and incorporates the
third-party components below. Data compiled 2026-11-25 (pypdfium2 added 2026-11-26) from PyPI metadata (versions pinned in `requirements.txt`),
wheel licence files (win_amd64, CPython 3.13), the npm lockfile (`webui/package-lock.json`) and upstream licence texts.
Assessment and open questions: [`docs/licence-audit.md`](docs/licence-audit.md). This is not legal advice.
Full licence texts ship inside the respective packages; source code of GPL/LGPL parts is available from the
upstream projects named below (exact versions as pinned).

**Generator:** the table at the end of this file ("Automatisch erfasste Distributionen") and the folder `licenses/<Distribution>/` with the
complete licence texts of all runtime dependencies are produced by [`scripts/gen_third_party_notices.py`](scripts/gen_third_party_notices.py)
(`build.ps1` runs it before PyInstaller; the folder is shipped next to the program, not checked in). The hand-written tables below add context
(bundled native libraries, notes); the generated part is authoritative for versions and licence files.
**Source code offer (AGPL-3.0-or-later):** https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner (also under "Hilfe -> Lizenz & Quelltext" in the app).

## Python (runtime)

| Component | Version | Licence | Project |
|---|---|---|---|
| pypdfium2 (Python bindings + bundled pdfium binary `pypdfium2_raw/pdfium.dll`) | 5.15.2 | BSD-3-Clause OR Apache-2.0 (bindings); pdfium BSD-3-Clause (c) The PDFium Authors; pdfium-binaries MIT (c) Benoit Blanchon; third-party code inside the binary per the wheel's `dist-info/licenses/BUILD_LICENSES/` (FreeType, HarfBuzz, ICU, lcms, libjpeg-turbo, OpenJPEG, libpng, libtiff, zlib, abseil, AGG, brotli, libyuv, simdutf, ...); replaces PyMuPDF/MuPDF (AGPL) since 2026-11-26; PDF rasterizing only | https://github.com/pypdfium2-team/pypdfium2 |
| Pillow | 13.0.0 | MIT-CMU | https://github.com/python-pillow/Pillow |
| pi-heif | 1.4.0 | BSD-3-Clause; Windows wheel bundles libheif (LGPL-3.0, v1.18.1) and libde265 (LGPL-3.0, v1.0.15) + MinGW runtime; no x265, no libaom (read-only HEIC decode); replaces pillow-heif (x265 GPL-2.0) since 2026-11-25 | https://github.com/bigcat88/pillow_heif |
| pikepdf | 10.7.3 | MPL-2.0; wheel bundles qpdf (Apache-2.0), libjpeg (IJG) | https://github.com/pikepdf/pikepdf |
| pypdf | 6.21.4 | BSD-3-Clause | https://github.com/py-pdf/pypdf |
| reportlab | 4.5.1 | BSD | https://www.reportlab.com/ |
| xhtml2pdf | 0.2.17 | Apache-2.0 | https://github.com/xhtml2pdf/xhtml2pdf |
| svglib (via xhtml2pdf) | 2.4.0 | LGPL-3.0-or-later | https://github.com/deeplook/svglib |
| python-bidi (via xhtml2pdf) | 0.6.12 | LGPL (COPYING + COPYING.LESSER) | https://github.com/MeirKriheli/python-bidi |
| pyHanko, pyhanko-certvalidator (via xhtml2pdf) | 0.38.2 / 0.33.0 | MIT | https://github.com/MatthiasValvekens/pyHanko |
| arabic-reshaper, html5lib, lxml, cssselect2, tinycss2, webencodings | see PyPI | MIT / MIT / BSD-3-Clause / BSD / BSD / BSD | PyPI |
| olefile | 0.47 | BSD-2-Clause (c) 2005-2023 Philippe Lagadec; reads Outlook .msg containers | https://github.com/decalage2/olefile |
| compressed-rtf | 1.0.7 | MIT (c) 2016 Dmitry Alimov; decompresses the RTF body of .msg files | https://github.com/delimitry/compressed_rtf |
| pywin32 | 312 | PSF | https://github.com/mhammond/pywin32 |
| pywebview | 6.2.1 | BSD-3-Clause (c) Roman Sirokov | https://github.com/r0x0r/pywebview |
| bottle, proxy_tools, typing_extensions | see PyPI | MIT / MIT / PSF-2.0 | PyPI |
| pythonnet | 3.1.0 | MIT | https://github.com/pythonnet/pythonnet |
| clr-loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| PyInstaller (build tool; bootloader GPL-2.0-or-later with special exception) | 6.20.0 | GPL-2.0-or-later with exception | https://pyinstaller.org |
| CPython runtime | 3.13 | PSF-2.0 | https://www.python.org |

## JavaScript (runtime, `webui/`)

| Component | Version | Licence |
|---|---|---|
| react, react-dom | 19.2.6 | MIT |
| scheduler | 0.27.0 | MIT |
| pdfjs-dist (PDF.js, Mozilla) | 6.5.438 | Apache-2.0 |
| - OpenJPEG (wasm) | bundled | BSD-2-Clause |
| - PDFium JBIG2 decoder (wasm) | bundled | BSD-3-Clause (c) The PDFium Authors |
| - qcms (wasm) | bundled | MIT (c) Mozilla, Marti Maria |
| - QuickJS | bundled | MIT (c) Fabrice Bellard, Charlie Gordon |
| - Adobe CMaps | bundled | BSD-3-Clause (c) Adobe Systems |
| - Foxit standard fonts | bundled | BSD (c) The PDFium Authors |
| - Liberation fonts | bundled | GPL-2.0 with font exception (c) Red Hat |
| - ICC profile | bundled | CC0 1.0 |

Licence files of the bundled PDF.js assets are shipped in `webui/dist/pdfjs/*/LICENSE*`.

## Own packages (same licence as this project)

`packages/datev-dokab`, `packages/belegtool-archives` and `packages/belegtool-compress`: AGPL-3.0-or-later.

## Trademarks

"DATEV" and "DATEVconnect" are trademarks of DATEV eG. This project is not affiliated with, endorsed or sponsored by DATEV eG.
Microsoft, Windows, Word, Excel, PowerPoint, Outlook and Edge/WebView2 are trademarks of Microsoft Corporation.

<!-- BEGIN GENERATED (scripts/gen_third_party_notices.py) -->

## Automatisch erfasste Distributionen

Erzeugt von [`scripts/gen_third_party_notices.py`](scripts/gen_third_party_notices.py) aus `requirements.txt` (+ rekursiven
Laufzeit-Abhängigkeiten laut installierten Metadaten) und `webui/package-lock.json`. Die vollständigen Lizenztexte liegen im
Ordner `licenses/<Distribution>/` (im Programmverzeichnis neben der exe; im Repo nicht eingecheckt, vom Build erzeugt).
Die Tabelle gilt für das venv, in dem das Skript lief (die eingecheckte Fassung stammt aus einem Entwicklungs-venv; Versionen
können von den Pins in `requirements.txt` abweichen). Maßgeblich ist die beim Build im Build-venv erzeugte Fassung (`build.ps1`).

### Python

| Distribution | Version | Lizenz | Lizenzdateien | Herkunft |
|---|---|---|---|---|
| aiohappyeyeballs | 2.7.1 | PSF-2.0 | 1 (`licenses/aiohappyeyeballs/`) | aiohttp |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT | 2 (`licenses/aiohttp/`) | pyHanko |
| aiosignal | 1.4.0 | Apache 2.0 | 1 (`licenses/aiosignal/`) | aiohttp |
| altgraph | 0.17.5 | MIT | 1 (`licenses/altgraph/`) | pyinstaller |
| arabic-reshaper | 3.1.0 | MIT | 1 (`licenses/arabic-reshaper/`) | xhtml2pdf |
| asn1crypto | 1.5.1 | MIT | 1 (`licenses/asn1crypto/`) | pyHanko |
| attrs | 26.1.0 | MIT | 1 (`licenses/attrs/`) | aiohttp |
| belegtool-archives | 0.1.0 | AGPL-3.0-or-later | 2 (`licenses/belegtool-archives/`) | requirements.txt |
| belegtool-compress | 0.1.0 | AGPL-3.0-or-later | 2 (`licenses/belegtool-compress/`) | requirements.txt |
| bottle | 0.13.4 | MIT | 1 (`licenses/bottle/`) | pywebview |
| certifi | 2026.11.20 | MPL-2.0 | 1 (`licenses/certifi/`) | pyhanko-certvalidator |
| cffi | 2.1.1 | MIT-0 | 1 (`licenses/cffi/`) | clr_loader |
| charset-normalizer | 3.5.3 | MIT | 1 (`licenses/charset-normalizer/`) | reportlab |
| clr_loader | 0.3.1 | unbekannt | 1 (`licenses/clr-loader/`) | pythonnet |
| compressed-rtf | 1.0.7 | MIT | 1 (`licenses/compressed-rtf/`) | requirements.txt |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | 3 (`licenses/cryptography/`) | pyHanko |
| cssselect2 | 0.10.1 | BSD License | 1 (`licenses/cssselect2/`) | svglib |
| datev-dokab | 0.1.0 | AGPL-3.0-or-later | 2 (`licenses/datev-dokab/`) | requirements.txt |
| frozenlist | 1.8.0 | Apache-2.0 | 1 (`licenses/frozenlist/`) | aiohttp |
| html5lib | 1.1 | MIT License | 1 (`licenses/html5lib/`) | xhtml2pdf |
| idna | 3.20 | BSD-3-Clause | 1 (`licenses/idna/`) | yarl |
| lxml | 6.1.3 | BSD-3-Clause | 2 (`licenses/lxml/`) | pikepdf |
| multidict | 7.2.1 | Apache-2.0 | 1 (`licenses/multidict/`) | aiohttp |
| olefile | 0.47 | BSD | 4 (`licenses/olefile/`) | requirements.txt |
| oscrypto | 1.3.0 | MIT | 1 (`licenses/oscrypto/`) | pyhanko-certvalidator |
| packaging | 26.4 | Apache-2.0 OR BSD-2-Clause | 3 (`licenses/packaging/`) | pyinstaller |
| pefile | 2024.8.26 | MIT | 1 (`licenses/pefile/`) | pyinstaller |
| pi_heif | 1.4.0 | BSD-3-Clause | 2 (`licenses/pi-heif/`) | requirements.txt |
| pikepdf | 10.18.2 | MPL-2.0 | 13 (`licenses/pikepdf/`) | requirements.txt |
| pillow | 13.0.0 | MIT-CMU | 1 (`licenses/pillow/`) | requirements.txt |
| propcache | 0.5.4 | Apache-2.0 | 2 (`licenses/propcache/`) | aiohttp |
| proxy_tools | 0.1.0 | MIT | keine (Sdist ohne Lizenzdatei; Metadaten: MIT (Jonathan Tushman), siehe docs/licence-audit.md) | pywebview |
| pycparser | 3.12 | BSD-3-Clause | 1 (`licenses/pycparser/`) | cffi |
| pyHanko | 0.38.2 | MIT | 2 (`licenses/pyhanko/`) | xhtml2pdf |
| pyhanko-certvalidator | 0.33.0 | MIT | 1 (`licenses/pyhanko-certvalidator/`) | xhtml2pdf |
| pyinstaller | 6.20.0 | GNU General Public License v2 (GPLv2) | 1 (`licenses/pyinstaller/`) | requirements.txt |
| pyinstaller-hooks-contrib | 2026.10 | Apache Software License; GNU General Public License v2 (GPLv2) | 1 (`licenses/pyinstaller-hooks-contrib/`) | pyinstaller |
| pypdf | 7.1.1 | BSD-3-Clause | 1 (`licenses/pypdf/`) | requirements.txt |
| pypdfium2 | 5.15.2 | BSD-3-Clause, Apache-2.0, dependency licenses | 37 (`licenses/pypdfium2/`) | requirements.txt |
| python-bidi | 0.6.12 | GNU Library or Lesser General Public License (LGPL) | 4 (`licenses/python-bidi/`) | xhtml2pdf |
| pythonnet | 3.1.0 | MIT | 2 (`licenses/pythonnet/`) | requirements.txt |
| pywebview | 6.2.1 | BSD License | 1 (`licenses/pywebview/`) | requirements.txt |
| pywin32 | 312 | PSF | 15 (`licenses/pywin32/`) | requirements.txt |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | 1 (`licenses/pywin32-ctypes/`) | pyinstaller |
| reportlab | 4.5.1 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. | 1 (`licenses/reportlab/`) | requirements.txt |
| setuptools | 84.2.1 | MIT | 6 (`licenses/setuptools/`) | pyinstaller |
| six | 1.17.0 | MIT | 1 (`licenses/six/`) | html5lib |
| svglib | 2.4.0 | LGPL-3.0-or-later | 1 (`licenses/svglib/`) | xhtml2pdf |
| tinycss2 | 1.5.1 | BSD License | 1 (`licenses/tinycss2/`) | svglib |
| typing_extensions | 4.16.0 | PSF-2.0 | 1 (`licenses/typing-extensions/`) | pypdf |
| tzlocal | 5.4.5 | MIT | 1 (`licenses/tzlocal/`) | pyHanko |
| uritools | 7.0.1 | MIT | 1 (`licenses/uritools/`) | pyhanko-certvalidator |
| webencodings | 0.6.1 | BSD License | 1 (`licenses/webencodings/`) | html5lib |
| xhtml2pdf | 0.2.17 | Apache Software License | 1 (`licenses/xhtml2pdf/`) | requirements.txt |
| yarl | 1.25.1 | Apache-2.0 | 2 (`licenses/yarl/`) | aiohttp |

### npm (Laufzeit, in `webui/dist` gebündelt)

| Paket | Version | Lizenz | Lizenzdateien |
|---|---|---|---|
| pdfjs-dist | 6.5.438 | Apache-2.0 | 1 (`licenses/npm/pdfjs-dist/`) |
| react | 19.2.6 | MIT | 1 (`licenses/npm/react/`) |
| react-dom | 19.2.6 | MIT | 1 (`licenses/npm/react-dom/`) |
| scheduler | 0.27.0 | MIT | 1 (`licenses/npm/scheduler/`) |

Optionale Node-only-Pakete (`@napi-rs/canvas*`, optionale Abhängigkeit von pdfjs-dist) landen nicht im Browser-Bundle und sind nicht erfasst.

PDF.js-Beipack (wasm/cmaps/Schriften): deren `LICENSE*`-Dateien liegen in `webui/dist/pdfjs/*/` (siehe oben).

<!-- END GENERATED -->
