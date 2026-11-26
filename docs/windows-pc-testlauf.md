# Testlauf auf dem Windows-Entwicklungs-PC (Stand 2026-11-25, Version 3.11.4)

> **Status: Skript auf Linux nur syntaktisch geprüft, auf Windows noch nicht gelaufen.**
> `scripts/windows_testlauf.ps1` konnte hier nicht ausgeführt werden (kein PowerShell verfügbar, nur Lesen/Klammerprüfung).
> Der erste Lauf auf dem PC ist zugleich der Test des Skripts: Skriptfehler (Phase meldet „Ausnahme" / „kein Ergebnis") bitte als solche melden.
> Grundlagen: [`test-automation-plan.md`](test-automation-plan.md), [`licence-audit.md`](licence-audit.md), [`pymupdf-extract-msg-ersatz.md`](pymupdf-extract-msg-ersatz.md), Abschnitte Build/Tests in `CLAUDE.md`.

**Zweck:** vor dem Austausch von PyMuPDF/extract-msg/pillow-heif (siehe Ersatz-Analyse) einen belegten Ist-Stand auf echtem Windows erheben
(Python-Suite, Pakete, Frontend, Build, Bundle-Inhalt, Start) und eine kurze manuelle Prüfung ergänzen. Ergebnis: eine Tabelle (Phase 6).

**Wer/wo:** der Eigentümer, auf seinem Entwicklungs-PC, ohne Admin-Rechte. Dauer grob 30-60 min mit Build (nicht gemessen).

## Schnellstart (Phasen 0-2 automatisch)

```powershell
cd <Pfad zum Repo>
git fetch origin
git checkout claude/exciting-hawking-ifv36m   # nach dem Merge stattdessen: git checkout master ; git pull
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows_testlauf.ps1
```

Optionen: `-SkipBuild` (ohne Phase 2) und `-SkipE2E` (nur vitest statt Playwright/CSP, kein Chromium-Download). Beispiel für einen schnellen Vorlauf:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows_testlauf.ps1 -SkipBuild -SkipE2E
```

Das Skript bricht bei einer fehlgeschlagenen Phase nicht ab, sondern protokolliert und läuft weiter.

- **Schreibt nur** in das Repo (`webui\node_modules`, `webui\dist`, `dist\`, `build\`, `.build_venv\`, `.pytest_cache`) und nach `testlauf-out\`
  (venvs, Logs unter `logs\`, pip-/npm-/Playwright-Caches, `testlauf-ergebnis.md`). Der Smoketest der Exe läuft mit umgeleitetem `%APPDATA%`
  (`testlauf-out\appdata`), schreibt also nicht in die echten Einstellungen.
- `testlauf-out\` steht **nicht** in `.gitignore` (bewusst nicht angefasst): nicht committen; `git status` zeigt den Ordner als „untracked".
- `build.ps1` löscht und baut `build\`, `dist\` und `.build_venv\` neu (bekanntes Verhalten, vgl. CLAUDE.md); danach fehlt pytest in `.build_venv` - der Testlauf nutzt dafür sein eigenes venv `testlauf-out\venv`.
- Ergebnisdatei: `testlauf-out\testlauf-ergebnis.md` (mit lokalen Pfaden geschwärzt: `<repo>`, `%USERPROFILE%`).

> **Erwartung auf diesem Stand:** HEIC läuft über `pi-heif` (kein `libx265`), daher müssen die Prüfungen `pi_heif` vorhanden, kein `pillow_heif`
> und keine `*x265*`-Datei **grün** sein; `datev`, `belegtool_archives`, `belegtool_compress`, `olefile` und `compressed_rtf` (eigener `.msg`-Leser) müssen im Bundle sein; `extract_msg` und `RTFDE` (GPLv3/LGPL, seit 2026-11-26 ersetzt) dürfen **nicht** mehr im Bundle sein. Weiterhin erwartbar nur als **Info**:
> `fitz` steckt noch im Bundle (siehe Lizenz-Audit; verschwindet erst mit dem späteren PyMuPDF-Ersatz). Rot bei den Punkten oben ist ein echter Befund - melden.

## Phase 0 - Voraussetzungen (Skript)

| Schritt | Zweck / Befehl (manuell) | Erwartung | Fehlerbild / melden |
|---|---|---|---|
| Git LFS | PDFs/Fixtures liegen in LFS. | `git lfs pull` ohne Fehler; `tests\data\input\compress_sample.pdf` beginnt mit `%PDF-`. | Datei ist ein LFS-Zeiger (Textdatei, ~130 Byte) → Tests scheitern massenhaft: melden „LFS-Zeiger". |
| Python 3.13 | `py -3.13 --version` | `Python 3.13.x` | Fehlt → `winget install Python.Python.3.13`. |
| Node / npm | `node --version` ; `npm --version` | Node 24 (CI-Stand), npm vorhanden | Version melden. |
| WebView2 + Edge | Registry-Schlüssel `EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` (Wert `pv`) | Version ≠ `0.0.0.0`; Edge vorhanden (nur für Testkit-Build) | „WebView2-Runtime nicht gefunden" → Exe-Start zeigt Fehlerfenster/leer; melden. |
| Branch | `git rev-parse --abbrev-ref HEAD` | `claude/exciting-hawking-ifv36m` oder `master` | Sonst Warnung (Skript wechselt den Branch nicht). |
| Office | Registry `Word.Application`, `Excel.Application`, `PowerPoint.Application` | Ergebnis wird nur festgehalten (ja/nein je App) | - |
| venv + Pakete | Skript: `py -3.13 -m venv testlauf-out\venv` ; `pip install -r requirements.txt -r requirements-dev.txt` | ohne Fehler | pip-Fehler: letzte Zeilen von `logs\p0-pip-install.log` (Paketname, Fehlermeldung). |
| Frontend | `cd webui` ; `npm ci` ; `npx playwright install chromium` | ohne Fehler | npm-Fehler: Log `p0-npm-ci.log`. |

Manuell zum Nachvollziehen (im Repo-Hauptordner):

```powershell
git lfs pull
py -3.13 -m venv testlauf-out\venv
testlauf-out\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
cd webui ; npm ci ; npx playwright install chromium ; cd ..
```

## Phase 1 - Automatische Tests (Skript)

**1a Python-Suite Hauptrepo** (inkl. `test_office_golden.py`, läuft nur mit Office, sonst automatisch übersprungen).

```powershell
testlauf-out\venv\Scripts\python.exe -m pytest -q -rs
```

Erwartung: Exitcode 0; CLAUDE.md nennt ~498 Tests (Richtwert, nicht zugesichert). Mit Office: Golden-Test nicht übersprungen. Fehlerbild: `FAILED …` → Testnamen + letzte Zeilen der Meldung; Auffällig viele Fehler in `test_file_lock*`/`test_host` → Windows-Eigenheit melden.

**1b Pakete isoliert** (je `packages\datev-dokab`, `belegtool-archives`, `belegtool-compress`; eigenes frisches venv ohne Hauptrepo, wie in `ci.yml`).

```powershell
cd packages\datev-dokab
py -3.13 -m venv ..\..\testlauf-out\pkgvenv\datev-dokab
..\..\testlauf-out\pkgvenv\datev-dokab\Scripts\python.exe -m pip install -e ".[dev]"
..\..\testlauf-out\pkgvenv\datev-dokab\Scripts\python.exe -m pytest
cd ..\..
```

Erwartung: grün je Paket (CI: ubuntu + windows). Fehlerbild: ein Import des Hauptrepos (`ModuleNotFoundError: core/infra/…`) → Paket ist nicht mehr eigenständig; melden mit Paketname.

**1c Lint, 1d Frontend-Tests, 1e Build**

```powershell
cd webui
npm run lint
npm run test:all
npm run build
cd ..
```

Erwartung: lint 0 Fehler; `test:all` = vitest (~281) + Playwright-e2e + CSP-Spec (`test:csp`, baut selbst) grün; Build erfolgreich. Fehlerbild: Playwright „browser not found" → `npx playwright install chromium`; CSP-Spec rot → melden (Produktions-`index.html` ohne/mit falscher CSP); Port 5178/5179 belegt (läuft `npm run dev`?) → Dev-Server beenden, wiederholen.

## Phase 2 - Build und Bundle-Prüfung (Skript, nicht mit `-SkipBuild`)

**2a Build**

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

Erwartung: endet mit „Fertig"; `dist\BelegTool\BelegTool.exe` existiert. Fehlerbild: PyInstaller-Fehlermeldung (`build.ps1` bricht dort nicht ab - das Skript prüft deshalb die Exe) → letzte 20 Zeilen von `logs\2a-build.log`.

**2b Bundle-Prüfung** (automatisch auf `dist\BelegTool\`; Details im Abschnitt „Details" der Ergebnisdatei)

| Prüfung | Erwartung | Befund → melden |
|---|---|---|
| `COPYING`, `LICENSE`, `THIRD_PARTY_NOTICES.md` | jeweils in `_internal\` und/oder neben der Exe; das Skript meldet **wo** (laut `belegtool.spec` landen sie in `_internal`; neben der Exe kopiert sie nur `packaging\build_msix.ps1`) | „nur `_internal`" ist für den normalen Build zu erwarten; **fehlt** eine Datei → melden |
| Module `datev`, `belegtool_archives`, `belegtool_compress`, `olefile`, `compressed_rtf` | im PYZ der Exe (Lesen über PyInstaller `CArchiveReader`, Fallback `build\belegtool\PYZ-00.toc`) | fehlt → melden (hidden import im `spec` greift nicht) |
| `pi_heif` | im Bundle | fehlt → melden (hidden import im `spec` greift nicht) |
| **kein** `pillow_heif` | nicht im Bundle | vorhanden → melden |
| **keine** Datei `*x265*` | keine | vorhanden → melden (Dateiname angeben; Lizenz-Audit rot) |
| `webui\dist\index.html` und `pdf-tool.html` | enthalten `Content-Security-Policy`; `pdfjs\wasm` vorhanden | fehlt → melden (leere/ungeschützte Oberfläche bzw. leere Scan-Seiten) |
| **kein** `extract_msg`, **kein** `RTFDE` | nicht im Bundle (verboten, seit dem MSG-Ersatz 2026-11-26) | vorhanden → melden (Lizenz-Audit rot) |

Manuell, falls nötig: `dir dist\BelegTool -Recurse -Filter *x265*` und `dist\BelegTool\_internal\webui\dist\index.html` im Editor nach `Content-Security-Policy` durchsuchen.

**2c Exe-Smoketest** (automatisch): Exe starten, 10 s warten, Prozess läuft noch, Fenster und `msedgewebview2.exe`-Prozess seit dem Start vorhanden, dann „Fenster schließen"; danach `belegtool_startup.log` (neben der Exe) prüfen: enthält „entering GUI loop", keine `Traceback`/`Exception`/`Error`-Zeilen.
Erwartung: OK. Fehlerbild: Prozess nach <10 s beendet, kein WebView2-Prozess (= UI leer), Startup-Log ohne „entering GUI loop" → melden mit den letzten Zeilen des Startup-Logs (`testlauf-out\logs\2c-belegtool_startup.log`; enthält Pfade der Exe - Benutzernamen schwärzen).
Zusatz: Startdauer „elapsed BEFORE main()" wird aus dem Log in die Ergebnisdatei übernommen (Hinweis auf AV/Mark-of-the-Web).

## Phase 3 - Echte GUI per CDP gegen WebView2 (nicht im Skript)

**Status: Skizze/To-do.** Laut Plan ([`test-automation-plan.md`](test-automation-plan.md), Ebene **G**) noch nicht implementiert: `tests\gui\launch_host.py` und die CDP-Specs existieren **nicht**; das Skript führt hier nichts aus und trägt „UEBERSPRUNGEN" ein. Beschriebenes Verfahren (zur Orientierung, nicht neu erfunden):

```powershell
# Skizze (nicht lauffähig, solange tests\gui fehlt):
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = '--remote-debugging-port=9222'
$env:WEBVIEW2_USER_DATA_FOLDER = "$PWD\testlauf-out\wv2-profil"   # eigener Ordner pro Lauf
# danach: Test-Launcher startet host.py (native Dialoge per Patch beantwortet), Playwright verbindet per connectOverCDP auf http://localhost:9222
```

Stolpersteine laut Plan: Läuft der Host-Prozess erhöht (Admin), ignoriert WebView2 ab Runtime 150 die Umgebungsvariable - dann nur HKLM-Policy `Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments` (braucht Admin; auf dem Entwicklungs-PC deshalb nicht Teil dieses Laufs). Ziel-Smoke laut Plan: Fenstertitel = Version, Datei öffnen, Umbenennen, Strg+S. Bis dahin ersetzen die Punkte in Phase 4 diese Ebene.

## Phase 4 - Manuell-kurz (Checkliste mit Soll)

Start: `dist\BelegTool\BelegTool.exe` (aus Phase 2) oder aus dem Quelltext `testlauf-out\venv\Scripts\python.exe host.py` (nach `npm run build`). Beispieldateien: `manual_tests\testpakete\<Fall>\Beispieldateien\` bzw. `tests\data\input\`. Haken setzen, Abweichung kurz notieren.

- [ ] **CSP / Oberfläche:** App starten. **Soll:** Fenster nicht leer, Baum + Symbolleiste sichtbar. Eine PDF importieren → **Vorschau rendert** (Seiten sichtbar). Rechtsklick → „In PDF-Tool öffnen" (oder `.pdf` direkt öffnen) → **PDF-Tool zeigt den Text-Layer** (Text im PDF markierbar). F12 ist nicht nötig. **Fehler:** leeres Fenster, graue Seiten, nicht markierbarer Text → melden (CSP blockiert vermutlich etwas).
- [ ] **Drop-Schutz:** eine `.html`- und eine `.svg`-Datei aus dem Explorer auf das **PDF-Tool-Fenster** ziehen. **Soll:** Fenster bleibt unverändert (keine Navigation, kein neuer Inhalt). **Fehler:** Fenster zeigt die Datei/Seite → melden (Dateityp).
- [ ] **Doppelklick `.belegtool`:** im Explorer doppelklicken (Zuordnung nur bei Store-/MSIX-Installation vorhanden; sonst „Öffnen mit" → Exe). **Soll:** App startet mit der Datei, Baum sichtbar. **Fehler:** App startet leer → melden.
- [ ] **Echte iPhone-HEIC** importieren (eigene Datei, nicht ins Repo/Meldung kopieren). **Soll:** 1 Seite, Bild in der Vorschau sichtbar. **Fehler:** Import-Meldung „nicht importierbar", 0 Seiten, schwarzes/leeres Bild → melden (HEIC-Variante: Live Photo? Format?). Besonders wichtig nach der pi-heif-Umstellung.
- [ ] **Mail mit Anhang** (`.eml` und `.msg`) importieren. **Soll:** Ordner mit Mailtext + Anhang(en) im Baum; Anhang-PDF öffnet. **Fehler:** Anhang fehlt (bes. bei weitergeleiteter `.msg`) → melden. Nach dem MSG-Ersatz: dieselbe Mail gegen den Ist-Stand vergleichen (Phase 5).
- [ ] **Echte Outlook-`.msg` (neuer eigener Leser, seit 2026-11-26)** - der Leser ist bisher **nur gegen synthetische Dateien** getestet (`packages\belegtool-archives\tests\msg_fixture.py`), **nicht** gegen echte Outlook-Mails. Deshalb mindestens diese **eigenen** Mails als `.msg` (Outlook: „Speichern unter → Outlook-Nachrichtenformat (Unicode)" bzw. auf den Desktop ziehen; nicht ins Repo und nicht in die Meldung kopieren) importieren und je Mail **Anzahl, Namen, Reihenfolge und Inhalt** der Knoten mit der Mail in Outlook vergleichen:
  1. nur Text (Nur-Text-Format), mit Umlauten/€/ß in Betreff und Text;
  2. HTML-Mail mit Formatierung und Bild im Text (Logo/Signatur) - das Bild darf als eigener Anhang erscheinen, der Text muss lesbar sein;
  3. RTF-Mail (Nachrichtenformat „Rich-Text") ohne HTML - erscheint als `.rtf`/Text, nicht leer;
  4. Mail mit **mehreren** Anhängen (PDF, Bild, Word/Excel, ZIP): jeder Anhang genau einmal, Dateiname mit Umlaut/Leerzeichen richtig, PDF öffnet;
  5. **weitergeleitete** Mail („WG:") mit dem Original **als Anhang** (eingebettete `.msg`): **Soll (neu):** Unterordner „….msg" mit Text und Anhängen der eingebetteten Mail; mit dem alten Leser war das „nicht importierbar";
  6. Mail ohne Betreff und Mail ohne Text (nur Anhang);
  7. ältere Mail (ANSI-Format, z. B. „Outlook-Nachrichtenformat" statt „Unicode", oder aus einem alten Archiv) mit Umlauten;
  8. Mail mit sehr großem Anhang (> 50 MB) und eine mit ≥ 20 Anhängen: kein Absturz, ggf. Hinweis „zu groß"/„Limit überschritten".

  **Fehler:** fehlender/zusätzlicher Anhang, falscher Name, vertauschte Reihenfolge, falsches Datum im Namen (Soll: Sendedatum in UTC, `JJJJ-MM-TT`), verstümmelte Umlaute im Text, leerer Mailtext obwohl Outlook Text zeigt, Meldung „Ungültige MSG-Datei" bei einer in Outlook lesbaren Mail → melden (Mailtyp/Outlook-Version/Format angeben, **keinen Mailinhalt**). Hilfe: `python scripts\diagnose_msg.py <datei.msg>` listet Betreff/Datum/Bodies/Anhänge, wie der Leser sie sieht.
- [ ] **Office-Datei** importieren - **nur mit Office** (Phase 0 „Office: ja"). **Soll:** 1+ Seiten, Text lesbar; ohne Office: verständliche Meldung „nicht importierbar". Wenn kein Office: „übersprungen" vermerken.
- [ ] **Kompression Farbscan:** `Farbscan_Rechnung_3_Seiten.pdf` (Tester-Kit) importieren, Vorschau-Kompression öffnen. **Soll:** mehrere Verfahren mit Größen; vor/nach notieren (KB); Seitenzahl nach dem Übernehmen gleich (3). **Fehler:** Seitenzahl anders, Seite fehlt/leer, Größe größer als Original → melden.
- [ ] **Export mit Inhaltsverzeichnis:** Export-Dialog, TOC an → speichern → Ergebnis-PDF in einem Viewer öffnen. **Soll:** Inhaltsverzeichnis vorn, Links springen zum Dokument, Lesezeichen vorhanden, Seitenzahlen stimmen.
- [ ] **Dateisperre kurz:**

```powershell
$env:BELEG_FILE_LOCK = '1'
.\dist\BelegTool\BelegTool.exe .\beispiel.belegtool
```

  Zweite Instanz mit derselben Datei starten. **Soll:** zweite meldet „in Benutzung" (deutsche Meldung), erste speichert normal. Danach `Remove-Item Env:\BELEG_FILE_LOCK`.
- [ ] **DATEV:** nur gegen eine **Testumgebung** (kein Produktivbestand!). Ohne Testumgebung: „übersprungen (keine Testumgebung)" vermerken - **nichts** gegen echte Mandanten testen. Zugangsdaten/Hostnamen nicht in die Meldung schreiben.

## Phase 5 - Paritätsvergleich nach dem PyMuPDF-Austausch (Platzhalter)

**Wird ergänzt, sobald der Austausch (pypdfium2 für Rastern/Maße, olefile-Eigenbau für `.msg`, pi-heif für HEIC) gemergt ist.** Vorgesehen laut [`pymupdf-extract-msg-ersatz.md`](pymupdf-extract-msg-ersatz.md) (Abschnitt 6, Qualitätssicherung):

- Golden-Vergleich alt (PyMuPDF) gegen neu (pypdfium2) auf `tests\data\input\`: Seitenzahl und Seitenmaße **exakt gleich**, Pixeldifferenz (SSIM/PSNR-Schwelle noch festzulegen).
- Kompressionsgrößen je Methode/DPI vorher/nachher protokollieren (Delta), „Lesbarkeit"-Verhalten stichprobenartig prüfen.
- `.msg`-Golden: dieselben (eigenen, nicht ins Repo gelegten) Outlook-Mails mit altem und neuem Leser; Betreff, Body, Anhänge, Weiterleitung, Embedded-Message vergleichen.
- Bundle-Prüfung (Phase 2b) muss dann grün sein: kein `extract_msg`/`RTFDE`, kein `pillow_heif`, keine `*x265*` (die `.msg`-/HEIC-Teile sind bereits umgesetzt und werden schon jetzt geprüft).
- Vorschau-Latenz auf dem PC (und stichprobenweise auf dem Terminalserver) wegen des Thread-Locks von pypdfium2.

Skript und Befehle dafür gibt es noch nicht - hier nichts ausführen.

## Phase 6 - Ergebnisse zurückmelden

1. Datei `testlauf-out\testlauf-ergebnis.md` öffnen (Tabelle Phase | Ergebnis | Dauer | Hinweis, plus Umgebung und Details der Bundle-Prüfung).
2. Phase 4 ergänzen (Vorlage unten) und beides **als Text in die Sitzung bzw. den PR-Kommentar kopieren**.
3. Nicht mitschicken: Benutzername, Pfade mit Benutzernamen, Hostnamen, DATEV-Daten, echte Mails/HEIC/Belege, komplette Logs. Logs nur auf Nachfrage (Ordner `testlauf-out\logs\`) und vorher durchsehen. Das Skript schwärzt Repo-Pfad und `%USERPROFILE%` selbst; die Ergebnisdatei trotzdem kurz überfliegen.

Vorlage für die manuellen Punkte:

| Phase 4 - Punkt | Ergebnis (OK / Abweichung / übersprungen) | Notiz (Dateityp, Größen, Meldungstext) |
|---|---|---|
| CSP: Oberfläche, Vorschau, PDF-Tool-Textlayer | | |
| Drop `.html`/`.svg` auf PDF-Tool | | |
| Doppelklick `.belegtool` | | |
| iPhone-HEIC | | |
| Mail `.eml` / `.msg` mit Anhang | | |
| Office-Import (nur mit Office) | | |
| Kompression Farbscan (KB vorher/nachher, Seiten) | | |
| Export mit Inhaltsverzeichnis | | |
| Dateisperre | | |
| DATEV (Testumgebung) | | |

Lauf-Parameter und Versionen stehen bereits im Kopf der Ergebnisdatei.
