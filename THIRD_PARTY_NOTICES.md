# Third-Party Notices

DigitalerUnterlagenOrdner (BelegTool) is licensed under AGPL-3.0-or-later (see `LICENSE`, full text in `COPYING`) and incorporates the
third-party components below. Data compiled 2026-11-25 from PyPI metadata (versions pinned in `requirements.txt`),
wheel licence files (win_amd64, CPython 3.13), the npm lockfile (`webui/package-lock.json`) and upstream licence texts.
Assessment and open questions: [`docs/licence-audit.md`](docs/licence-audit.md). This is not legal advice.
Full licence texts ship inside the respective packages; source code of GPL/LGPL parts is available from the
upstream projects named below (exact versions as pinned).

## Python (runtime)

| Component | Version | Licence | Project |
|---|---|---|---|
| PyMuPDF / MuPDF | 1.27.2.3 | AGPL-3.0 (dual: Artifex commercial) | https://github.com/pymupdf/PyMuPDF |
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
