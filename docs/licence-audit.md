# Lizenz-Audit (Stand 2026-11-26, Version 3.11.4)

> **Keine Rechtsberatung.** Technische Bestandsaufnahme. Alles, was als „Fakt" steht, ist mit Quelle belegt
> (PyPI-JSON-Metadaten der gepinnten Versionen, Lizenzdateien in den heruntergeladenen Win-x64-Wheels
> bzw. im npm-Tarball, `package-lock.json`, Dateien im Repo). **Unsicheres ist als „juristisch klären" markiert.**
> Methode: `pypi.org/pypi/<paket>/<version>/json`, `pip download --platform win_amd64 --python-version 3.13`
> (Wheel-Inhalte), `npm pack pdfjs-dist@6.5.438`, Upstream-Seiten (pymupdf.readthedocs.io, pyinstaller.org, x265-COPYING).

## 1. Zusammenfassung (Ampeln)

Bewertet wird zweifach: **AGPL** = Verteilung des Hauptrepos unter AGPL-3.0(-or-later);
**Komm.** = Eignung für die kommerzielle Zusatzlizenz des Eigentümers (`LICENSE_COMMERCIAL.md`, proprietäre Weitergabe/Einbindung).

| Ampel | Punkt |
|---|---|
| ~~ROT~~ erledigt 2026-11-26 | ~~**PyMuPDF/MuPDF** (AGPL-3.0 oder Artifex-Kommerzlizenz)~~ → Rastern läuft über **pypdfium2 5.15.2** (PyPI-Metadaten `License: BSD-3-Clause, Apache-2.0, dependency licenses`; Win-x64-Wheel `py3-none-win_amd64` mit `pypdfium2_raw/pdfium.dll` und `dist-info/licenses/BUILD_LICENSES/*`, per `pip download --platform win_amd64 --only-binary=:all: --no-deps` + `unzip -l` am 2026-11-26 belegt). Schnittstelle `belegtool_compress.raster`; PyMuPDF nur noch Dev-/Test-Orakel (`requirements-dev.txt`, Extra `oracle`), nicht im Bundle (`belegtool.spec` excludes `fitz`/`pymupdf`). Guard: `tests/test_no_agpl_pdf_deps.py`; Laufzeit ohne PyMuPDF: `scripts/smoke_no_pymupdf.py` (CI-Job `no-pymupdf-runtime`). Messbelege/Abweichungen: [`pdfium-spike.md`](pdfium-spike.md). Vorbehalt: PyInstaller-Bündelung der `pdfium.dll` und Render unter RDP/echten Scans nur auf Windows prüfbar (Testlauf Phase 5). |
| ~~ROT~~ erledigt 2026-11-26 | ~~extract-msg 0.55.0 (GPL-3.0) + transitiv RTFDE (LGPL-3)~~ → ersetzt durch den eigenen `.msg`-Leser `belegtool-archives/belegtool_archives/msg_reader.py` auf **olefile 0.47 (BSD-2-Clause)** + **compressed-rtf 1.0.7 (MIT)** (PyPI-Metadaten + Wheel-Lizenztexte am 2026-11-26 geprüft: olefile `License: BSD`, Klassifikator „BSD License“, `LICENSE.txt` = Zwei-Klausel-BSD, (c) Philippe Lagadec; compressed-rtf `license_expression: MIT`, MIT-Text, (c) 2016 Dmitry Alimov). `extract-msg`/`RTFDE` sind aus `requirements.txt`, Paket-Metadaten, Code und Bundle (`belegtool.spec` excludes) entfernt. Guard: `tests/test_no_gpl_msg_deps.py`. Vorbehalt: Reader nur gegen synthetische `.msg` getestet (Windows-Testlauf Phase 4: echte Outlook-Mails). |
| ~~ROT~~ erledigt 2026-11-25 | ~~pillow-heif 1.3.0 Win-Wheel bündelt `libx265` (GPLv2)~~ → ersetzt durch **pi-heif 1.4.0** (Win-Wheel cp313: nur libheif/libde265 LGPLv3 + MinGW-Runtime, **keine x265-DLL**, per `pip download --platform win_amd64 --python-version 3.13 --only-binary=:all:` + `unzip -l` belegt; `LICENSES_bundled.txt`: „binary wheels: LGPLv3"). Guard: `tests/test_no_gpl_codec_wheels.py`. Offen: Verhalten mit echten iPhone-HEICs unter PyInstaller/Windows ungeprüft. |
| GELB (technisch umgesetzt 2026-11-26, Windows ungeprüft) | **LGPL-Komponenten** im Bundle: `svglib` (LGPL-3.0-or-later, via xhtml2pdf), `python-bidi` (LGPL, via xhtml2pdf), libheif/libde265 (LGPL-3); RTFDE ist seit 2026-11-26 entfernt. Mit AGPL kein Problem; für proprietäre Weitergabe: Austauschbarkeit/Quelltext-Angebot/Lizenztext nötig. Umgesetzt: Lizenztexte im Bundle (`licenses/`), svglib/bidi als `.py` statt im PYZ, DLLs/`.pyd` liegen ohnehin getrennt in `_internal/` - Details in Abschnitt 5a. Offen: Windows-Wirkung + juristische Bewertung (Abschnitt 8). |
| ~~GELB~~ erledigt 2026-11-26 (Windows-Build ungeprüft) | ~~**Kein Third-Party-Hinweis** im ausgelieferten Bundle/MSIX~~ → `THIRD_PARTY_NOTICES.md` (Tabelle vom Generator `scripts/gen_third_party_notices.py`) + Ordner `licenses/<Distribution>/` mit den Lizenztexten **aller** Python-Distributionen (inkl. rekursiver Abhängigkeiten, pdfium/Skia-`BUILD_LICENSES` aus dem pypdfium2-Wheel) und der npm-Laufzeitpakete; `belegtool.spec` nimmt beides auf, `build_msix.ps1` kopiert es neben die Exe, `build.ps1` erzeugt es vor PyInstaller; ein Paket ohne Lizenztext bricht den Build ab (Ausnahmeliste mit Begründung: aktuell nur `proxy_tools`, Sdist ohne Lizenzdatei, Metadaten MIT). Quelltext-Angebot (AGPL §13) + Link in der App: Hilfe → „Lizenz & Quelltext“. Test: `tests/test_third_party_notices.py`. |
| GELB | **`LICENSE` ist nur ein Kurztext (34 Zeilen) mit Link, nicht der volle AGPL-3.0-Text** (Hauptrepo und beide Pakete identisch, md5 `6f1c0339…`). AGPL verlangt, den Lizenztext mitzugeben. |
| GELB | pdf.js-Beipack: Liberation-Schriften (`standard_fonts/LICENSE_LIBERATION` = GPL v2 + Font-Ausnahme, Red Hat) – als eigenständige Datendateien (Aggregation) wohl unkritisch, juristisch klären. |
| GRÜN | Pillow (MIT-CMU), pikepdf (MPL-2.0; qpdf Apache-2.0), pypdf (BSD-3), reportlab (BSD), xhtml2pdf (Apache-2.0), pywin32 (PSF), pywebview (BSD-3), pythonnet/clr-loader (MIT), PyInstaller (GPLv2+ mit Bootloader-Ausnahme), React/ReactDOM/scheduler (MIT), pdfjs-dist (Apache-2.0), `datev-dokab` (keine Abhängigkeiten). |

Mit der AGPL des Hauptrepos sind nach aktueller Datenlage **alle** geprüften Abhängigkeiten vereinbar (Vorbehalt: x265-„or later"). Nach dem Ersatz von libx265 (2026-11-25), extract-msg/RTFDE und PyMuPDF (2026-11-26) bleibt **kein roter Punkt** mehr; die Hinweis-/CLA-/SPDX-Punkte sind technisch erledigt (2026-11-26, Pakete), offen sind die juristische Klärung (Abschnitt 8), der Abgleich des `LICENSE`-Kurztexts mit dem AGPL-Text und die SPDX-Köpfe im Hauptrepo. Die kommerzielle Zusatzlizenz hängt nicht mehr an Artifex.

## 2. Abhängigkeiten – Python (`requirements.txt`, gepinnte Versionen)

| Paket (Version) | Lizenz (Beleg) | AGPL | Komm. | Anmerkung |
|---|---|---|---|---|
| pypdfium2 5.15.2 (ersetzt PyMuPDF 1.27.2.3) | PyPI-METADATA: „License: BSD-3-Clause, Apache-2.0, dependency licenses“. Wheel `py3-none-win_amd64` enthält `pypdfium2_raw/pdfium.dll` (7,8 MB) und `dist-info/licenses/`: `LICENSES/{Apache-2.0,BSD-3-Clause,CC-BY-4.0}.txt` sowie `BUILD_LICENSES/` mit pdfium (BSD-3, (c) The PDFium Authors), pdfium-binaries (MIT, (c) Benoit Blanchon), FreeType, HarfBuzz, ICU, lcms, libjpeg-turbo (IJG/BSD), OpenJPEG, libpng, libtiff, zlib, abseil, agg23, dragonbox, fast_float, highway, simdutf, brotli, libyuv (+ `v8_xfa/*` nur für die V8/XFA-Variante des Binärs; ob die ausgelieferte DLL V8 enthält, nicht im Binär geprüft). **Keine Skia-/Chromium-Gesamtlizenz im Wheel** (pdfium rendert mit AGG). | grün | grün | Permissiv: Hinweis-/Copyright-Pflicht, in `THIRD_PARTY_NOTICES.md`. PyMuPDF (AGPL/Artifex) bleibt nur als Dev-/Test-Orakel (nicht ausgeliefert). |
| Pillow 13.0.0 | MIT-CMU (PyPI `license_expression`) | grün | grün | Copyright-Hinweis beilegen. |
| pi-heif 1.4.0 (ersetzt pillow-heif 1.3.0) | Python-Code BSD-3-Clause; Win-Wheel „LGPLv3" (`LICENSES_bundled.txt`): libheif LGPLv3 (v1.18.1), libde265 LGPLv3 (v1.0.15); **kein x265, kein libaom** (Wheel-Inhalt belegt: libde265/libheif/libgcc_s/libstdc++/libwinpthread-DLLs) | gelb | **gelb** (war rot) | Nur Lesen (Decode); kein Encoder. LGPL-Auflage wie svglib/bidi. Test-Guard `tests/test_no_gpl_codec_wheels.py`. Ungeprüft: echte iPhone-HEICs unter Python 3.13/PyInstaller/Windows. |
| pikepdf 10.7.3 | MPL-2.0; Wheel enthält qpdf (Apache-2.0), libjpeg (IJG), MSVC-Runtime (`licenses-for-wheels.txt`) | grün | grün | MPL: Änderungen an pikepdf-Dateien offenlegen (wir ändern nichts). |
| pypdf 6.21.4 | BSD-3-Clause | grün | grün | |
| reportlab 4.5.1 | BSD (PyPI) | grün | grün | |
| xhtml2pdf 0.2.17 | Apache-2.0 (PyPI) | grün | grün | Zieht transitiv die folgenden Zeilen. |
| ↳ svglib 2.4.0 | **LGPL-3.0-or-later** | gelb | gelb | Austausch/Relink-Pflicht bei proprietärer Weitergabe. |
| ↳ python-bidi 0.6.12 | **LGPL** (Wheel enthält `COPYING` + `COPYING.LESSER`; Rust-Erweiterung `.pyd`) | gelb | gelb | Als separate `.pyd` im onedir austauschbar. |
| ↳ pyHanko 0.38.2, pyhanko-certvalidator 0.33.0 | MIT | grün | grün | Zieht aiohttp, cryptography (Apache-2.0 OR BSD-3), oscrypto/asn1crypto/uritools (MIT), tzlocal (MIT), certifi (nicht einzeln geprüft). |
| ↳ arabic-reshaper 3.1.0, html5lib 1.1, lxml 6.1.3, cssselect2, tinycss2, webencodings | MIT / MIT / BSD-3 / BSD | grün | grün | |
| ~~extract-msg 0.55.0~~ (erledigt 2026-11-26) | war **GPL** (GPLv3, transitiv RTFDE 0.1.2.2 LGPLv3) | – | war rot | Ersetzt, nicht mehr in `requirements.txt`/Bundle (s. Ampel oben). |
| olefile 0.47 | **BSD-2-Clause** (PyPI: `License: BSD`; Wheel-`LICENSE.txt` = zwei Klauseln, Philippe Lagadec; Upload 2023-12-01) | grün | grün | Rein Python, keine Abhängigkeiten. Neu: Extra `msg` des Pakets `belegtool-archives` + in `requirements.txt` gepinnt. |
| compressed-rtf 1.0.7 | **MIT** (PyPI `license_expression: MIT`; Lizenztext im Wheel, (c) 2016 Dmitry Alimov; Upload 2025-03-24) | grün | grün | Rein Python, keine Abhängigkeiten (LZFu/MELA-Dekompression). |
| pywin32 312 | PSF (PyPI-Klassifikator) | grün | grün | |
| pywebview 6.2.1 | BSD-3-Clause (Roman Sirokov) | grün | grün | Zieht bottle (MIT), proxy_tools (MIT), typing_extensions (PSF-2.0). |
| pythonnet 3.1.0 | MIT | grün | grün | clr-loader 0.3.1: PyPI-Metadaten leer, **Upstream-LICENSE = MIT** (github.com/pythonnet/clr-loader); cffi nicht einzeln geprüft. |
| pyinstaller 6.20.0 | GPLv2-or-later **mit Sonderausnahme** (PyPI); laut pyinstaller.org dürfen erzeugte Apps unter beliebiger Lizenz stehen, „as long as it complies with the licenses of your dependencies"; keine Lizenzbeilage nötig | grün | grün | Build-Werkzeug. pyinstaller-hooks-contrib 2026.10 (Apache-2.0 / GPLv2): Runtime-Hook-Details nicht separat geprüft (niedrige Priorität, juristisch klären). |
| datev-dokab (lokal) | AGPL-3.0-or-later, **keine** Abhängigkeiten | grün | grün | Nur Eigentümer-Code. |
| belegtool-archives (lokal) | AGPL-3.0-or-later, keine harten Abhängigkeiten; Extra `msg` = olefile (BSD-2) + compressed-rtf (MIT) | grün | grün | Seit 2026-11-26 auch mit Extra grün (extract-msg ersetzt). |

## 3. Abhängigkeiten – npm (Laufzeit, `webui/package-lock.json`)

| Paket | Lizenz | AGPL | Komm. |
|---|---|---|---|
| react 19.2.6, react-dom 19.2.6, scheduler 0.27.0 | MIT (lock-Feld `license`) | grün | grün |
| pdfjs-dist 6.5.438 | Apache-2.0 (Tarball-`LICENSE`). Beipack: `wasm/` OpenJPEG (BSD-2), PDFium-JBIG2 (BSD-3), qcms (MIT), QuickJS (MIT); `cmaps/` Adobe (BSD-3); `iccs/` CC0; `standard_fonts/` Foxit (BSD), **Liberation (GPLv2 + Font-Ausnahme)** | grün | gelb (Liberation) |
| @napi-rs/canvas 1.1.0 (optional, Plattform-Binärpakete) | MIT | grün | grün (Annahme: nicht im Browser-Bundle) |

Dev-/Build-Abhängigkeiten (vite, vitest, playwright, eslint …) landen nicht im Bundle und wurden nicht einzeln geprüft.

## 4. Konsistenz im Repo

- **LICENSE-Dateien identisch:** Haupt-`LICENSE`, `datev-dokab/LICENSE`, `belegtool-archives/LICENSE` haben dieselbe md5 (belegt).
- **Inhalt der LICENSE:** nur Kurzhinweis („either version 3 … or (at your option) any later version") plus Link; **der volle AGPL-Text fehlt** → To-do (Datei wie beauftragt nicht verändert).
- **„only" vs. „or later":** Hauptrepo-`LICENSE` = *or later*; Pakete (`pyproject.toml`, READMEs) = `AGPL-3.0-or-later` → konsistent. Aber `README.md` (Abschnitt License) und `CONTRIBUTING.md` sagen nur „AGPLv3" ohne „or later" → angleichen. Das Hauptrepo hat keine `pyproject.toml`/SPDX-Angabe.
- **SPDX-/Copyright-Header:** ~~in keiner Quelldatei~~ **erledigt für die drei Pakete (2026-11-26):** alle `.py` unter `packages/*/` (inkl. `tests/`, 54 Dateien ergänzt) tragen `# SPDX-License-Identifier: AGPL-3.0-or-later` + `# SPDX-FileCopyrightText: Copyright (C) 2026 Tobias Heinrich` (Zeile wörtlich aus `LICENSE`). Skript `scripts/add_spdx_headers.py` (idempotent, `--check`), Test `tests/test_spdx_headers.py`. **Hauptrepo erledigt 2026-11-26 (Freigabe des Eigentümers):** dieselben Köpfe in allen Python-Quellen von `core/`, `services/`, `formats/`, `infra/`, `universal_importer/`, `tools/`, `scripts/`, `tests/`, `host.py`, `version_info.py`, `datev_probe.py` (130 Dateien, nur Einfügungen; `python scripts/add_spdx_headers.py [--check]`; Test deckt zusätzlich jede git-verfolgte `.py`-Datei ab). **Offen:** JS/JSX in `webui/src/` (`// SPDX-…`) – braucht ein eigenes Skript.
- **CLA:** ~~steht nur in `CONTRIBUTING.md` des Hauptrepos~~ **erledigt (2026-11-26):** jedes der drei Pakete hat jetzt eine eigene `CONTRIBUTING.md` mit dem CLA-Abschnitt **wörtlich** aus dem Hauptrepo (nichts umformuliert); die Paket-READMEs verweisen darauf; `pyproject.toml` (`license-files`) unverändert. Test `tests/test_package_cla.py` vergleicht Text und Hash mit dem Hauptrepo (schlägt bei jeder Abweichung fehl; ändert der Eigentümer den Wortlaut, müssen alle vier Stellen gemeinsam angepasst werden). Die CLA gewährt nur ein *nicht-exklusives* Recht („use, reproduce, modify, redistribute under any license"); ob das für Unterlizenzierung im Rahmen der Doppellizenz reicht (Sublizenzrecht, Zusicherung der Rechteinhaberschaft, Arbeitgeberrechte) → **juristisch klären**.
- **Kommerzielle Lizenz:** `LICENSE_COMMERCIAL.md` regelt Drittkomponenten nicht; Paket-READMEs verweisen korrekt auf die kommerzielle Lizenz im Hauptrepo (mit Kontakt).
- **Kein Befund:** `vendor/` steht in `.gitignore`; `git log --all -- vendor` ist leer und es gibt keine getrackten `openapi`/`swagger`-Dateien → **keine DATEV-Spezifikation in der Git-Historie** (für die lokal vorhandenen Refs).

## 5. Ausgelieferte Hinweise (Bundle/MSIX)

- ~~`belegtool.spec` packt nur `webui/dist` + pywebview/pythonnet/clr_loader-Daten; keine Lizenz-/NOTICE-Datei.~~ Seit 2026-11-26 zusätzlich `COPYING`, `LICENSE`, `THIRD_PARTY_NOTICES.md` und der generierte Ordner `licenses/` (explizit, unabhängig davon, ob PyInstaller `*.dist-info`-Lizenzdateien mitnimmt - das ist weiterhin **nicht geprüft**, Windows-Build nötig).
- Über `webui/dist/pdfjs/{cmaps,standard_fonts,wasm,iccs}` (Vite-Plugin `pdfjsAssets` kopiert die Ordner komplett) gelangen deren `LICENSE*`-Dateien ins Bundle. Der Apache-2.0-Text von pdf.js selbst und die MIT-Hinweise von React sind **nicht garantiert** im JS-Bundle enthalten (Minifizierung kann Lizenzkommentare entfernen) → seit 2026-11-26 liegen die `LICENSE`-Dateien von pdfjs-dist, react, react-dom und scheduler zusätzlich unter `licenses/npm/<Paket>/` (Generator liest `webui/node_modules`; fehlt der Ordner, steht „nicht erfasst“ in der Tabelle).
- ~~Neu: `THIRD_PARTY_NOTICES.md` (Wurzel). Offen: in `belegtool.spec`/`packaging/build_msix.ps1` ins Bundle aufnehmen und im Store-Listing/„Über“ verlinken.~~ **Erledigt 2026-11-26:** `belegtool.spec` (datas `THIRD_PARTY_NOTICES.md` + `licenses/`), `packaging/build_msix.ps1` (kopiert `licenses/` neben die Exe), `build.ps1` (Generator vor PyInstaller), Store-Listing (DE+EN) und App-Hilfe verlinken Quelltext + Hinweise. Windows-Build selbst **nicht ausgeführt** (nur Syntax/Text-Tests); Prüfpunkte stehen im Windows-Testlauf (Phase 2b).

### 5a. LGPL: Austausch/Relinking

Ziel: Wer die LGPL-Bibliotheken im ausgelieferten Bundle durch eine eigene Fassung ersetzen will, kann das, ohne neu zu bauen. Bewertung der PyInstaller-onedir-Ausgabe (`dist\BelegTool\_internal\`, PyInstaller 6.20.0):

| Komponente | Form im Bundle | Austauschbar? |
|---|---|---|
| libheif, libde265 (LGPL-3, in pi-heif-Wheel) | getrennte DLLs im Wheel-Verzeichnis (`pi_heif.libs/`) → als einzelne Dateien in `_internal/` | ja: DLL ersetzen (gleiche ABI/Version-Familie vorausgesetzt) |
| python-bidi (LGPL, Rust-Erweiterung) | `bidi/bidi.*.pyd` getrennte Datei; die Python-Teile (`bidi/*.py`) sind seit 2026-11-26 per `module_collection_mode` als `.py` gesammelt | ja: `.pyd` und `.py` ersetzen |
| svglib (LGPL-3.0-or-later, reines Python) | **vorher:** `.pyc` im PYZ-Archiv der Exe (nicht einzeln ersetzbar). **jetzt:** `belegtool.spec` setzt `module_collection_mode={'svglib': 'py', 'bidi': 'py'}` → `_internal/svglib/*.py` als Dateien | ja: `_internal/svglib/` durch eine eigene Fassung ersetzen |

Belege: `Analysis(module_collection_mode=...)` ist in PyInstaller 6.20.0 vorhanden (`PyInstaller/building/build_main.py`, Werte `'pyz'` (Standard), `'pyc'`, `'py'`, `'pyz+py'`; je Paket rekursiv inkl. Untermodule). Es muss `'py'` sein, nicht `'pyz+py'` (dann gewänne beim Import die PYZ-Kopie). **Auf Linux nachgestellt** (Mini-App mit svglib 2.4.0 + python-bidi 0.6.12, PyInstaller 6.20.0, onedir): `svglib.svglib.__file__` zeigt auf `_internal/svglib/svglib.py`, `bidi/` enthält `.py` + die `.so`; eine angehängte `print`-Zeile in `_internal/svglib/__init__.py` wurde beim nächsten Start ausgeführt (= Ersetzung wirkt). **Windows: ungeprüft** (Pfade/`.pyd`, Defender, MSIX-Paketintegrität). Der Windows-Testlauf prüft `licenses\` und `_internal\svglib\svglib.py` (Phase 2b).

**Anleitung für Nutzer (Relinking):** (1) Quelltext der Bibliothek aus dem Upstream-Repo in der in `THIRD_PARTY_NOTICES.md` genannten Version holen (svglib: https://github.com/deeplook/svglib, python-bidi: https://github.com/MeirKriheli/python-bidi); (2) geänderte Fassung als Ordner `svglib/` (bzw. `bidi/`) in `<Installationsordner>\_internal\` an die Stelle des vorhandenen kopieren (bei python-bidi inkl. passender `.pyd`); (3) BelegTool neu starten - der Import findet die Dateien im Dateisystem, das PYZ enthält keine Kopie mehr. Bei der MSIX/Store-Version ist der Installationsordner schreibgeschützt; dort ist der Austausch nur über die zip-Fassung (GitHub Release) oder den Selbstbau (`build.ps1`) möglich. Das Hauptprogramm ist AGPL und im Quelltext verfügbar; ein „Neu-Linken“ gegen proprietären Code entfällt damit. Juristische Bewertung (reicht das, PYZ-Restfragen) bleibt in Abschnitt 8.

## 6. Rechte Dritter, Assets, Marken

- `assets/icon.svg|ico|png`, `webui/public/favicon.svg`: einfache Eigen-Vektorgrafik erscheinend; Herkunft **nicht belegt** → Eigentümer bestätigt.
- `webui/public/icons.svg`, `webui/src/assets/{react,vite}.svg`, `hero.png`: Vite-React-Vorlage (MIT; Annahme anhand der Namen). `hero.png` ist in `webui/src` nicht referenziert → ggf. entfernen.
- `packaging/screenshots/*.png`: Annahme Eigen-Screenshots.
- `tests/data/input` und Tester-Kit `manual_tests/testpakete/`: laut CLAUDE.md synthetisch/reproduzierbar (`scripts/testkit/samples.py`), Fixtures selbst erstellt; Herkunft einzelner Binärdateien nicht Datei für Datei geprüft.
- Marke **„DATEV“**: `datev-dokab/README.md` hatte **keinen** Nicht-Verbunden-Hinweis → ergänzt. **2026-11-26:** der Satz „Dieses Projekt steht in keiner Verbindung zur DATEV eG; DATEV ist eine eingetragene Marke der DATEV eG.“ (+ englische Entsprechung) steht jetzt auch im Haupt-`README.md` (Abschnitt Trademarks), in `packaging/store-listing.md` (DE+EN) und in der App-Hilfe (Abschnitt „Lizenz & Quelltext“, DE/EN/FR/ES). `PRIVACY.md` erwähnt DATEV nicht → unverändert. Paketname `datev-dokab`: **bleibt** (Entscheidung des Eigentümers: „DATEV im Namen ist ok“); die juristische Restfrage steht in Abschnitt 8.

## 7. To-dos (nach Priorität)

1. Geschäftsmodell-Entscheidung für die Kommerzlizenz: (a) ~~Artifex-Lizenz für PyMuPDF oder andere PDF-Engine~~ erledigt 2026-11-26 (pypdfium2/pdfium); (b) ~~`extract-msg` entfernen/ersetzen~~ erledigt 2026-11-26 (olefile-Eigenbau); (c) Bundle ohne `libx265` bzw. anderer HEIC-Weg.
2. Vollständigen AGPL-3.0-Text als `LICENSE` ins Hauptrepo und die Pakete - **offen: Abgleich** des `COPYING`-Volltexts mit dem offiziellen AGPL-3.0-Text des FSF (nur Eigentümer/Juristen; nicht mit Werkzeug geprüft) und Entscheidung, ob `LICENSE` (Kurztext) so bleibt.
3. ~~`THIRD_PARTY_NOTICES.md` ins Bundle/MSIX; Apache-2.0-/MIT-Texte (pdf.js, React); Quelltext-Hinweis~~ **erledigt 2026-11-26** (Generator + `licenses/`, npm-Texte von pdfjs-dist/react/react-dom/scheduler, Hilfe-Link; Windows-Build ungeprüft).
4. ~~SPDX-Header Pakete; `CONTRIBUTING.md` (CLA) in die Pakete~~ **erledigt 2026-11-26**. SPDX-Köpfe Hauptrepo (Python) **erledigt 2026-11-26**. **Offen:** SPDX-Köpfe für JS/JSX in `webui/src/`; „or later“ in `README.md`/`CONTRIBUTING.md`-Fließtext angleichen; `LICENSE_COMMERCIAL.md` um Drittkomponenten-Klausel ergänzen.
5. ~~Nicht-Verbunden-Hinweis in README/Store-Listing~~ **erledigt 2026-11-26** (README, Store-Listing DE+EN, Hilfe).
6. Rest = Juristisches (Abschnitt 8).

## 8. Juristisch klären

- ~~Trägt die Dual-Lizenz bei einem Kern, der PyMuPDF nutzt?~~ Gegenstandslos seit 2026-11-26 (PyMuPDF nicht mehr im Produkt). Offen bleibt nur die Frage nach den gelben LGPL-Punkten.
- x265: GPL-2.0-only oder -or-later? Vereinbarkeit des pillow-heif-Win-Wheels (GPLv2) mit AGPL-3.0 beim Bündeln im PyInstaller-Verbund. (Seit 2026-11-25 gegenstandslos für das Bundle: x265 entfällt mit pi-heif.)
- LGPL-3 (svglib, python-bidi, libheif, libde265, RTFDE) in PyInstaller-onedir/MSIX: genügt der Dateiaustausch, wie ist das PYZ-Archiv zu bewerten, was muss der Quelltext-Hinweis enthalten?
- Liberation-Schriften (GPLv2 + Ausnahme, im pdf.js-Beipack) in einem proprietär weitergegebenen Bundle.
- CLA: Reicht „nicht-exklusiv" für Unterlizenzierung; Beiträge Dritter in den ausgelagerten Repos.
- Marke DATEV im Paketnamen/README; Wortlaut des Nicht-Verbunden-Hinweises.
- Ob AGPL §13 (Netzwerknutzung) für eine reine Desktop-App überhaupt relevant ist.
