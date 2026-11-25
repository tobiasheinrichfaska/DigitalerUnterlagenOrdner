# Lizenz-Audit (Stand 2026-11-25, Version 3.11.4)

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
| ROT (Komm.) | **PyMuPDF/MuPDF** (AGPL-3.0 oder Artifex-Kommerzlizenz): Der Eigentümer kann Dritten keine Nicht-AGPL-Lizenz am Gesamtprodukt einräumen, ohne selbst eine Artifex-Lizenz zu besitzen. Der Kern (Rendering, Engine) hängt an `fitz`. |
| ROT (Komm.) | **extract-msg 0.55.0 (GPL-3.0, hart in `requirements.txt` gepinnt)** + transitiv **RTFDE (LGPL-3)**: das ausgelieferte Bundle enthält GPL-Code. Die Kommerzlizenz kann das nicht abdecken (so schon in CLAUDE.md, „Findings 2026-10-18"). |
| ~~ROT~~ erledigt 2026-11-25 | ~~pillow-heif 1.3.0 Win-Wheel bündelt `libx265` (GPLv2)~~ → ersetzt durch **pi-heif 1.4.0** (Win-Wheel cp313: nur libheif/libde265 LGPLv3 + MinGW-Runtime, **keine x265-DLL**, per `pip download --platform win_amd64 --python-version 3.13 --only-binary=:all:` + `unzip -l` belegt; `LICENSES_bundled.txt`: „binary wheels: LGPLv3"). Guard: `tests/test_no_gpl_codec_wheels.py`. Offen: Verhalten mit echten iPhone-HEICs unter PyInstaller/Windows ungeprüft. |
| GELB | **LGPL-Komponenten** im Bundle: `svglib` (LGPL-3.0-or-later, via xhtml2pdf), `python-bidi` (LGPL, via xhtml2pdf), libheif/libde265 (LGPL-3), RTFDE. Mit AGPL kein Problem; für proprietäre Weitergabe: Austauschbarkeit/Quelltext-Angebot/Lizenztext nötig. |
| GELB | **Kein Third-Party-Hinweis** im ausgelieferten Bundle/MSIX (vorher keine `THIRD_PARTY_NOTICES`). Jetzt als `THIRD_PARTY_NOTICES.md` im Repo angelegt; Einbindung ins Bundle/MSIX noch offen (To-dos). |
| GELB | **`LICENSE` ist nur ein Kurztext (34 Zeilen) mit Link, nicht der volle AGPL-3.0-Text** (Hauptrepo und beide Pakete identisch, md5 `6f1c0339…`). AGPL verlangt, den Lizenztext mitzugeben. |
| GELB | pdf.js-Beipack: Liberation-Schriften (`standard_fonts/LICENSE_LIBERATION` = GPL v2 + Font-Ausnahme, Red Hat) – als eigenständige Datendateien (Aggregation) wohl unkritisch, juristisch klären. |
| GRÜN | Pillow (MIT-CMU), pikepdf (MPL-2.0; qpdf Apache-2.0), pypdf (BSD-3), reportlab (BSD), xhtml2pdf (Apache-2.0), pywin32 (PSF), pywebview (BSD-3), pythonnet/clr-loader (MIT), PyInstaller (GPLv2+ mit Bootloader-Ausnahme), React/ReactDOM/scheduler (MIT), pdfjs-dist (Apache-2.0), `datev-dokab` (keine Abhängigkeiten). |

Mit der AGPL des Hauptrepos sind nach aktueller Datenlage **alle** geprüften Abhängigkeiten vereinbar (Vorbehalt: x265-„or later"). Die **kommerzielle Zusatzlizenz ist für das ausgelieferte Gesamtprodukt derzeit nicht ohne Weiteres haltbar** (PyMuPDF, extract-msg, libx265).

## 2. Abhängigkeiten – Python (`requirements.txt`, gepinnte Versionen)

| Paket (Version) | Lizenz (Beleg) | AGPL | Komm. | Anmerkung |
|---|---|---|---|---|
| PyMuPDF 1.27.2.3 | „GNU AGPL 3.0 or Artifex Commercial License" (Wheel-METADATA/`COPYING`; pymupdf.readthedocs.io: „available under both, open-source AGPL and commercial license agreements"; Artifex als Kommerzlizenzgeber) | grün | **rot** | Kommerzlizenz bei Artifex (artifex.com/licensing) nötig, sobald nicht-AGPL weitergegeben wird. |
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
| extract-msg 0.55.0 | **GPL** (`LICENSE.txt` im Wheel = GPLv3-Text) | grün (GPLv3 ↔ AGPLv3 kombinierbar, GPLv3 §13) | **rot** | Transitiv: olefile (BSD), tzlocal, compressed-rtf (MIT), ebcdic (BSD-2), beautifulsoup4 (MIT), red-black-tree-mod (MIT), **RTFDE 0.1.2.2 (LGPLv3)** → lark (MIT), oletools (BSD). Im Hauptrepo hart gepinnt (anders als das optionale Extra im Paket `belegtool-archives`). |
| pywin32 312 | PSF (PyPI-Klassifikator) | grün | grün | |
| pywebview 6.2.1 | BSD-3-Clause (Roman Sirokov) | grün | grün | Zieht bottle (MIT), proxy_tools (MIT), typing_extensions (PSF-2.0). |
| pythonnet 3.1.0 | MIT | grün | grün | clr-loader 0.3.1: PyPI-Metadaten leer, **Upstream-LICENSE = MIT** (github.com/pythonnet/clr-loader); cffi nicht einzeln geprüft. |
| pyinstaller 6.20.0 | GPLv2-or-later **mit Sonderausnahme** (PyPI); laut pyinstaller.org dürfen erzeugte Apps unter beliebiger Lizenz stehen, „as long as it complies with the licenses of your dependencies"; keine Lizenzbeilage nötig | grün | grün | Build-Werkzeug. pyinstaller-hooks-contrib 2026.10 (Apache-2.0 / GPLv2): Runtime-Hook-Details nicht separat geprüft (niedrige Priorität, juristisch klären). |
| datev-dokab (lokal) | AGPL-3.0-or-later, **keine** Abhängigkeiten | grün | grün | Nur Eigentümer-Code. |
| belegtool-archives (lokal) | AGPL-3.0-or-later, keine harten Abhängigkeiten; Extra `msg` = extract-msg (GPLv3) | grün | grün (ohne Extra) | README warnt korrekt vor GPLv3 beim Extra. |

## 3. Abhängigkeiten – npm (Laufzeit, `webui/package-lock.json`)

| Paket | Lizenz | AGPL | Komm. |
|---|---|---|---|
| react 19.2.6, react-dom 19.2.6, scheduler 0.27.0 | MIT (lock-Feld `license`) | grün | grün |
| pdfjs-dist 6.5.438 | Apache-2.0 (Tarball-`LICENSE`). Beipack: `wasm/` OpenJPEG (BSD-2), PDFium-JBIG2 (BSD-3), qcms (MIT), QuickJS (MIT); `cmaps/` Adobe (BSD-3); `iccs/` CC0; `standard_fonts/` Foxit (BSD), **Liberation (GPLv2 + Font-Ausnahme)** | grün | gelb (Liberation) |
| @napi-rs/canvas 1.1.0 (optional, Plattform-Binärpakete) | MIT | grün | grün (Annahme: nicht im Browser-Bundle) |

Dev-/Build-Abhängigkeiten (vite, vitest, playwright, eslint …) landen nicht im Bundle und wurden nicht einzeln geprüft.

## 4. Konsistenz im Repo

- **LICENSE-Dateien identisch:** Haupt-`LICENSE`, `packages/datev-dokab/LICENSE`, `packages/belegtool-archives/LICENSE` haben dieselbe md5 (belegt).
- **Inhalt der LICENSE:** nur Kurzhinweis („either version 3 … or (at your option) any later version") plus Link; **der volle AGPL-Text fehlt** → To-do (Datei wie beauftragt nicht verändert).
- **„only" vs. „or later":** Hauptrepo-`LICENSE` = *or later*; Pakete (`pyproject.toml`, READMEs) = `AGPL-3.0-or-later` → konsistent. Aber `README.md` (Abschnitt License) und `CONTRIBUTING.md` sagen nur „AGPLv3" ohne „or later" → angleichen. Das Hauptrepo hat keine `pyproject.toml`/SPDX-Angabe.
- **SPDX-/Copyright-Header:** in keiner Python-/JS-Quelldatei (nur `tests/make_office_fixtures.py` enthält das Wort „Copyright"). Empfehlung: `SPDX-License-Identifier: AGPL-3.0-or-later` + Copyright in den Paketdateien, spätestens vor der Auslagerung.
- **CLA:** steht nur in `CONTRIBUTING.md` des Hauptrepos. Beide Paket-READMEs paraphrasieren sie und verweisen aufs Hauptrepo; **in den ausgelagerten Repos fehlt eine eigene `CONTRIBUTING.md` mit dem CLA-Text** → mitnehmen. Die CLA gewährt nur ein *nicht-exklusives* Recht („use, reproduce, modify, redistribute under any license"); ob das für Unterlizenzierung im Rahmen der Doppellizenz reicht (Sublizenzrecht, Zusicherung der Rechteinhaberschaft, Arbeitgeberrechte) → **juristisch klären**.
- **Kommerzielle Lizenz:** `LICENSE_COMMERCIAL.md` regelt Drittkomponenten nicht; Paket-READMEs verweisen korrekt auf die kommerzielle Lizenz im Hauptrepo (mit Kontakt).
- **Kein Befund:** `vendor/` steht in `.gitignore`; `git log --all -- vendor` ist leer und es gibt keine getrackten `openapi`/`swagger`-Dateien → **keine DATEV-Spezifikation in der Git-Historie** (für die lokal vorhandenen Refs).

## 5. Ausgelieferte Hinweise (Bundle/MSIX)

- `belegtool.spec` packt als `datas` nur `webui/dist` + pywebview/pythonnet/clr_loader-Daten; **keine Lizenz-/NOTICE-Datei** wird explizit ergänzt. Ob PyInstaller die `*.dist-info`-Lizenzdateien der Wheels mitnimmt, ist **nicht geprüft** (Windows-Build nötig).
- Über `webui/dist/pdfjs/{cmaps,standard_fonts,wasm,iccs}` (Vite-Plugin `pdfjsAssets` kopiert die Ordner komplett) gelangen deren `LICENSE*`-Dateien ins Bundle. Der Apache-2.0-Text von pdf.js selbst und die MIT-Hinweise von React sind **nicht garantiert** enthalten (Minifizierung kann Lizenzkommentare entfernen) → prüfen.
- Neu: `THIRD_PARTY_NOTICES.md` (Wurzel). Offen: in `belegtool.spec`/`packaging/build_msix.ps1` ins Bundle aufnehmen und im Store-Listing/„Über" verlinken.

## 6. Rechte Dritter, Assets, Marken

- `assets/icon.svg|ico|png`, `webui/public/favicon.svg`: einfache Eigen-Vektorgrafik erscheinend; Herkunft **nicht belegt** → Eigentümer bestätigt.
- `webui/public/icons.svg`, `webui/src/assets/{react,vite}.svg`, `hero.png`: Vite-React-Vorlage (MIT; Annahme anhand der Namen). `hero.png` ist in `webui/src` nicht referenziert → ggf. entfernen.
- `packaging/screenshots/*.png`: Annahme Eigen-Screenshots.
- `tests/data/input` und Tester-Kit `manual_tests/testpakete/`: laut CLAUDE.md synthetisch/reproduzierbar (`scripts/testkit/samples.py`), Fixtures selbst erstellt; Herkunft einzelner Binärdateien nicht Datei für Datei geprüft.
- Marke **„DATEV"**: `packages/datev-dokab/README.md` hatte **keinen** Nicht-Verbunden-Hinweis → ergänzt. Haupt-`README.md`, `PRIVACY.md`, `packaging/store-listing.md` erwähnen DATEV nicht (grep) – bei Bewerbung der Funktion ergänzen. Der Paketname `datev-dokab` kann über Nominative Fair Use hinausgehen → **juristisch klären** (ggf. umbenennen).

## 7. To-dos (nach Priorität)

1. Geschäftsmodell-Entscheidung für die Kommerzlizenz: (a) Artifex-Lizenz für PyMuPDF oder andere PDF-Engine; (b) `extract-msg` entfernen/ersetzen (olefile-Eigenbau, s. CLAUDE.md); (c) Bundle ohne `libx265` bzw. anderer HEIC-Weg.
2. Vollständigen AGPL-3.0-Text als `LICENSE` ins Hauptrepo und beide Pakete.
3. `THIRD_PARTY_NOTICES.md` ins Bundle/MSIX; Apache-2.0-/MIT-Texte (pdf.js, React) sicherstellen; Quelltext-Hinweis für LGPL/GPL-Teile (Link + Pins).
4. SPDX-Header; „or later" in README/CONTRIBUTING angleichen; `CONTRIBUTING.md` (CLA) in die ausgelagerten Repos; `LICENSE_COMMERCIAL.md` um Drittkomponenten-Klausel ergänzen.
5. Nicht-Verbunden-Hinweis auch in README/Store-Listing, falls DATEV beworben wird.

## 8. Juristisch klären

- Trägt die Dual-Lizenz (AGPL + Eigentümer-Kommerzlizenz) bei einem Kern, der PyMuPDF (AGPL, Artifex-Kommerzlizenz) nutzt? Kann der Eigentümer ohne Artifex-Lizenz proprietär lizenzieren?
- x265: GPL-2.0-only oder -or-later? Vereinbarkeit des pillow-heif-Win-Wheels (GPLv2) mit AGPL-3.0 beim Bündeln im PyInstaller-Verbund. (Seit 2026-11-25 gegenstandslos für das Bundle: x265 entfällt mit pi-heif.)
- LGPL-3 (svglib, python-bidi, libheif, libde265, RTFDE) in PyInstaller-onedir/MSIX: genügt der Dateiaustausch, wie ist das PYZ-Archiv zu bewerten, was muss der Quelltext-Hinweis enthalten?
- Liberation-Schriften (GPLv2 + Ausnahme, im pdf.js-Beipack) in einem proprietär weitergegebenen Bundle.
- CLA: Reicht „nicht-exklusiv" für Unterlizenzierung; Beiträge Dritter in den ausgelagerten Repos.
- Marke DATEV im Paketnamen/README; Wortlaut des Nicht-Verbunden-Hinweises.
- Ob AGPL §13 (Netzwerknutzung) für eine reine Desktop-App überhaupt relevant ist.
