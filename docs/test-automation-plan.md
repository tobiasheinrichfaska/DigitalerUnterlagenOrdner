# Testautomatisierung – Plan (Stand 2026-11-25)

Frage A: Welche der 85 manuellen Windows-Tests (`manual_tests/00…10`) lassen sich automatisieren?
Frage B: Was soll bei GitHub Actions laufen? Der Workflow dazu: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Zusammenfassung

| | Fälle | Anteil |
|---|---|---|
| **ja** – komplett automatisierbar | **70** | 82 % |
| **teilweise** – Kern automatisierbar, ein kleiner Rest bleibt menschlich | **15** | 18 % |
| **nein** – rein menschlich | 0 | 0 % |

- Von den 70 „ja" ist der **Logikkern bereits durch vorhandene Tests abgedeckt** (✓ in der Tabelle, nach Dateinamen
  und CLAUDE.md eingeschätzt, **nicht** Zeile für Zeile gegen die Anleitungen geprüft). Neu zu bauen (○) sind vor allem die
  **echten GUI-Abläufe** (Ebene G) und das Fake-DATEV (Ebene D).
- **Menschlich bleibt** ein Kurzprotokoll von **etwa 12 Prüfpunkten** statt 85 Anleitungen: Store-Installation/-Update/Deinstallation
  (INST-01..03), Explorer-Doppelklick (04·MT-15b), Mehrmonitor (05·MT-34b), „fühlt sich flüssig an" (05·MT-39), Layout-Optik
  (07·MT-55), echter System-Browser bei PDF-Link (09·MT-54), Office-Import auf einem PC ohne self-hosted Runner (01·MT-03c)
  und die **Live-Gegenprobe gegen ein echtes DATEVconnect** (6 Fälle der Gruppe 10, je ein Durchlauf pro Release).
- **Größte Hebel:** (1) Ebene **P** auf `windows-latest` (CoreApi headless) deckt Import, Baum, Komprimierung, Speichern, Export,
  Sperre ab – die meisten Tests existieren schon, es fehlt nur der CI-Lauf. (2) Ebene **G**: Playwright per CDP gegen die echte
  `host.py`-Oberfläche – ersetzt die „Klick-durch"-Anleitungen (Bereiche 05/07/08). (3) **Fake-DATEVconnect** (HTTPS, lokal) für
  curl/Negotiate-Pfad und Konfliktfälle. (4) Die generierten Beispieldateien (`scripts/testkit/samples.py`) sind reproduzierbar –
  dieselben Dateien dienen als Testeingaben.

## Mechanismen (Spalte „Mechanismus")

| Kürzel | Ebene | Läuft auf | Status |
|---|---|---|---|
| **P** | pytest, `CoreApi` headless (Windows-only Module → `windows-latest`) | GitHub-hosted Windows | ✓ vorhanden (`tests/`), CI neu |
| **V** | Vitest/jsdom gegen gemockte `window.pywebview.api` | ubuntu | ✓ vorhanden (kein `vi.mock`, siehe CLAUDE.md) |
| **E** | Playwright/Chromium mit Stub-Bridge (`webui/e2e`) | ubuntu | ✓ vorhanden (5 Specs), erweiterbar |
| **G** | **Echte GUI**: `host.py` startet, WebView2 mit `--remote-debugging-port`, Playwright `connectOverCDP`; native Dialoge per Launcher-Patch ersetzt | `windows-latest` (interaktive Sitzung nötig) | ○ neu, **hier nicht verifizierbar** |
| **D** | Fake-DATEVconnect (lokaler HTTPS-Server, Self-signed, `401 WWW-Authenticate: Negotiate` → 200) gegen `curl.exe --negotiate` | `windows-latest` | ○ neu, nicht verifiziert |
| **M** | MSIX-/Exe-Smoke (Build, Start, Sideload mit Selbstsignatur) | `windows-latest`, manuell/nächtlich | ○ neu, nicht verifiziert |
| **O** | Office-COM (`test_office_golden.py`) | **self-hosted** Windows mit Office | ✓ vorhanden, Runner fehlt |
| **H** | Mensch | – | – |

## Belastbare Rahmenbedingungen (recherchiert)

| Frage | Befund | Quelle |
|---|---|---|
| `windows-latest` | = **Windows Server 2025** (`windows-2025`, auch `windows-2025-vs2026`) | [actions/runner-images](https://github.com/actions/runner-images) |
| Software im Image | Python 3.12 (3.13 im Tool-Cache → `setup-python` nutzen), Node 22/24, Git LFS 3.8, Edge + Chrome; **WebView2 nicht in der Software-Liste** | [Windows2025-Readme](https://github.com/actions/runner-images/blob/main/images/windows/Windows2025-Readme.md) |
| WebView2-Runtime auf dem Runner | Maintainer: Image installiert/konfiguriert WebView2 **nicht**; vorhanden ist die Evergreen-Runtime des Basisimages (Version driftet, Auto-Update aus). Auf 2025 wurde in einem Issue Runtime 152 in der Registry gefunden. **Nicht zusichern – im Job prüfen (`BLBeacon`-Registry) und sonst Bootstrapper nachinstallieren (~1–2 min)** | [runner-images #9538](https://github.com/actions/runner-images/issues/9538), [#14738](https://github.com/actions/runner-images/issues/14738) |
| Interaktive Desktop-Sitzung | Gemeldet, dass hosted Windows-Runner eine interaktive Sitzung (kleine Auflösung, ca. 1024×768) haben und SendInput/UIA-Tools funktionieren – **informell, keine offizielle Zusage**; nur per Probelauf klärbar | [win-uia #3](https://github.com/JelleBuning/win-uia/issues/3), [autoclicker #83](https://github.com/TMHSDigital/autoclicker/issues/83) |
| Playwright ↔ WebView2 | Offiziell: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222`, dann `connectOverCDP`; **eigenes `WEBVIEW2_USER_DATA_FOLDER` pro Lauf** | [Playwright WebView2](https://playwright.dev/python/docs/webview2) |
| **Stolperstein Runner = Admin** | Seit Runtime 150 ignoriert eine **erhöhte (High-Integrity) Host-Prozess** die Umgebungsvariable und HKCU-Policy; gelten nur **HKLM-Policy** `HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments` oder API-Argumente. Der Runner läuft als `runneradmin` → **HKLM-Policy im Job setzen** (Plan B: festes Runtime-Fixed-Version <150) | [WebView2Feedback #5645](https://github.com/MicrosoftEdge/WebView2Feedback/issues/5645) |
| msedgedriver/WebDriver gegen WebView2 | auf `windows-2025-vs2026` kaputt (Runtime ≥133, upstream-Regression) → **CDP statt WebDriver** | [runner-images #14738](https://github.com/actions/runner-images/issues/14738) |
| Windows Sandbox | In gehosteten Runnern **nicht zu erwarten** (Nested Virtualization) – nicht recherchiert/belegt; stattdessen MSIX-Sideload direkt auf dem Runner | – |
| `curl --negotiate` gegen lokalen Server | `host.py`/`transport.py` rufen `System32\curl.exe --negotiate -u :` (SSPI). Ein Fake-Server braucht keine Kerberos-Validierung: er antwortet auf Anfrage ohne `Authorization` mit `401 + WWW-Authenticate: Negotiate` und akzeptiert danach jeden `Authorization: Negotiate …`-Header. **Ob SSPI auf dem Runner (kein Domänenkonto, NTLM-Fallback) ein Token liefert, ist ungetestet.** Fallback: `make_urllib_transport` + injizierter Transport (P) | Code: `datev/transport.py` |

**Technische Voraussetzung für G ohne Produktivcode-Änderung:** Alle nativen Dialoge laufen über
`win.create_file_dialog` / `win.create_confirmation_dialog` (`host.py`). Ein Test-Launcher
(`tests/gui/launch_host.py`) patcht diese beiden Methoden vor `host.main()` mit skriptgesteuerten Antworten
(Datei-Pfade, „OK"/„Abbrechen"). Alternativ pywinauto/UIA für echte Dialoge (fragil, nur bei Bedarf).
`host._configure_webview2_env` lässt eine gesetzte `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` unangetastet (kompatibel).

## Was bei GitHub laufen soll (Frage B)

| Job | Runner | Inhalt | Wann |
|---|---|---|---|
| `pytest` | windows-latest | `pytest` (Python 3.13, requirements + requirements-dev, LFS-Fixtures). Muss Windows sein: 24 Tests brauchen Windows-Module; Office-Tests skippen automatisch | jeder Push/PR |
| `webui` | ubuntu-latest | `npm ci`, `npm run lint`, `npm test`, `npm run build` | jeder Push/PR |
| `e2e` | ubuntu-latest | `npx playwright install --with-deps chromium`, `npm run test:e2e` (echte LFS-PDFs) | jeder Push/PR |
| `exe-smoke` (manuell) | windows-latest | `npm run build` + PyInstaller laut `belegtool.spec`, prüft Exe + gebündelte `webui/dist` (inkl. PDF.js-wasm) | `workflow_dispatch` |
| *später* `gui` (G) | windows-latest | Launcher + CDP-Tests, HKLM-Policy, WebView2-Check | nach Probelauf, erst nächtlich |
| *später* `datev-fake` (D) | windows-latest | Fake-Server + `curl.exe --negotiate` | nach Probelauf |
| *später* Office (O) | self-hosted | `pytest -m office` | nächtlich/Release |

Bewusst **nicht** in CI: Office (kein Office auf hosted Runnern), DATEV (nur Fake), Store-Installation.
Hinweis: Vitest-Pool `vmThreads` ist in `vite.config.js` fest verdrahtet (siehe CLAUDE.md) – CI ruft nur `npm test` auf.

## Klassifikation aller 85 Fälle

Spalte „Auto?": ja / teilweise. Mechanismus: ✓ = Kern bereits durch vorhandene Tests, ○ = noch zu bauen. „Rest" = was beim Menschen bleibt.

### 00 Installation

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 00·INST-01 | Aus Store installieren und starten | teilweise | M: MSIX-Sideload (Selbstsignatur) + Start ○; Rest: Store-Seite, Preis, SmartScreen | win / H |
| 00·INST-02 | Installierte Version feststellen | teilweise | P: Titel = `version_info`, Manifest `X.Y.Z.0` = Version ○; Rest: Store-Update | win / H |
| 00·INST-03 | Deinstallieren | teilweise | M: `Remove-AppxPackage`, `.belegtool` bleibt lesbares PDF (✓ Roundtrip) ○; Rest: Startmenü/Store | win / H |

### 01 Import

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 01·MT-01 | Einzelnes PDF importieren | ja | P ✓ import + Undo; V ✓ Drop-Zonen; G ○ Dialog-Stub | win/ubuntu |
| 01·MT-01b | .belegtool in Dokument importieren | ja | P ✓ `test_import_belegtool_root` | win |
| 01·MT-02 | Bild importieren (6 Formate) | ja | P ✓ Beispieldateien via `samples.py` | win |
| 01·MT-03 | E-Mail (.eml/.msg) | ja | P ✓ `test_msg_import`, `msg_fixture` | win |
| 01·MT-03b | Text/HTML | ja | P ✓ | win |
| 01·MT-03c | Office-Dateien | teilweise | O ✓ `test_office_golden`; „ohne Office"-Meldung P ✓; Rest: Menschen-PC ohne Runner | self-hosted / win |
| 01·MT-04 | Archive zip/tar | ja | P ✓ `test_archive_*` | win |
| 01·MT-05 | Getarnte EXE abgelehnt | ja | P ✓ (bekannte Abweichung Schritt 1: strict-xfail) | win |
| 01·MT-05b | Nicht unterstützt / Teilimport | ja | P ✓ + V `messages.js` | win |
| 01·MT-06 | Verschachtelte Container | ja | P ✓ `test_archive_nested`, `test_archive_total_depth` | win |

### 02 Baum bearbeiten

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 02·MT-06 | Splitten | ja | P ✓ `test_split_*`; V Menü-Sichtbarkeit ✓ | win/ubuntu |
| 02·MT-07 | Zusammenführen | ja | P ✓ `test_split_merge`; V ✓ `mergeableIds` | win/ubuntu |
| 02·MT-08 | Ordner anlegen/umbenennen/löschen | ja | V ✓ `App.addfolder`, `lib/tree.js`; P ✓ | ubuntu |
| 02·MT-08b | Mehrfachauswahl + Status | ja | V ✓ `App.select`; P ✓ | ubuntu |
| 02·MT-09 | Verschieben mit Maus, Ebene | ja | E ✓ `dragdrop.spec` (Geometrie) ausbaubar ○; V ✓ | ubuntu |
| 02·MT-09b | Mehrere gleichzeitig verschieben | ja | V ✓ `App.moveresolver`; E ○ | ubuntu |
| 02·MT-09c | Unzulässiges Verschieben | ja | P ✓ `test_commands`; V ✓ Meldung | win/ubuntu |
| 02·MT-09d | Undo/Redo über mehrere Schritte | ja | P ✓ `test_session` | win |

### 03 Vorschau, Komprimierung, Drehen, Status

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 03·MT-10 | Vorschau und Zoom | ja | E ✓ `virtualization.spec` + `zoomAnchor.test`; Zoom-Anker im Browser ○ | ubuntu |
| 03·MT-11 | DPI-Regler, Verfahren | ja | P ✓ `compress_options`; V ✓ `PreviewControls` | win/ubuntu |
| 03·MT-12 | Übernehmen und zurücksetzen | ja | P ✓ `test_engine_commands` | win |
| 03·MT-12b | Drehen | ja | P ✓; V ✓ Reihenfolge ↺/↻ | win/ubuntu |
| 03·MT-13 | Status-Punkte | ja | V ✓ `status.test.js` | ubuntu |

### 04 Export, Speichern, Öffnen

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 04·MT-14 | Export mit TOC, Aufteilen | ja | P ✓ `test_export_split`, `test_export_index` (pikepdf prüft Links/Lesezeichen) | win |
| 04·MT-15 | Speichern und wieder öffnen | ja | P ✓ `test_belegtool_roundtrip`, `test_reload_coherence` | win |
| 04·MT-15d | Beschädigte Datei | ja | P ✓ `test_load_integrity`, `test_testkit` (Defekte_Mappe) | win |
| 04·MT-15b | Doppelklick / Dateizuordnung | teilweise | P ✓ `_startup_target_from_argv`; M ○ Zuordnung nach Sideload; Rest: Explorer-Symbol | win / H |
| 04·MT-15c | Einzelnes PDF mit „Öffnen" | ja | P ✓ | win |
| 04·MT-17 | Komprimierung verwirft Quelle | ja | P ✓ `test_reload_coherence` | win |
| 04·MT-19 | Speichern-Dialog Alternativen | ja | V ✓ `SaveDialog`; P ✓ `test_variant_persistence` (Größenvergleich) | win/ubuntu |

### 05 Bedienoberfläche

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 05·MT-30 | Starten, öffnen, speichern | ja | G ○ (Start, Öffnen per Argument, Umbenennen, Strg+S); P ✓ | win-GUI |
| 05·MT-31 | Importieren: Button, Ziehen, Ziel | ja | V ✓ `useOsFileDrop`; E ✓ DnD-Zonen; Explorer-Drop echt: G ○ (synthetisch) | ubuntu |
| 05·MT-32 | Baum bearbeiten (Mix) | ja | V ✓ + P ✓ (siehe 02) | ubuntu/win |
| 05·MT-33 | Komprimierungs-Vorschau | ja | V ✓ + P ✓ | ubuntu/win |
| 05·MT-34 | Mehrere Fenster | ja | P ✓ `test_host` (uid-Bindung); G ○ zweites Fenster | win(-GUI) |
| 05·MT-34b | Fenstergeometrie/Monitor | teilweise | P ✓ `test_window_geometry` (abgesteckter Monitor rein logisch); Rest: echte Mehrmonitor-Anordnung | win / H |
| 05·MT-35 | Schutz vor Verlust | ja | P ✓ `test_host` (`_bind_close` mit Fake-Dialog); G ○ | win |
| 05·MT-36 | Export mit TOC | ja | P ✓ (siehe 04·MT-14); V ✓ `ExportDialog` | win/ubuntu |
| 05·MT-37 | Tastenkürzel und Zoom | ja | V ✓ `useKeyboard`; E ○ Strg+Mausrad | ubuntu |
| 05·MT-39 | Großes PDF, Vorschau ohne Wartezeit | teilweise | E ✓ Virtualisierung, P ✓ `render_service`; Zeitschwellen auf Shared-Runner flaky → nur grobe Grenze; Rest: „fühlt sich flüssig an" | ubuntu / H |
| 05·MT-40 | Tastatur-Umbau, Zuklappen | ja | V ✓ `treeNav`, `useKeyboard` | ubuntu |
| 05·MT-41 | Tags (Filter, Gruppen, Mehrfach) | ja | V ✓ `tags.test`, `TagEditor`, `TagViewBar`; P ✓ `test_tag_many` | ubuntu/win |

### 06 Statusleiste, Cache, Komprimierungsablauf

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 06·MT-40 | Statusleiste/Cache-Anzeige | ja | V ✓ `StatusBar`; P ✓ `render_stats` | ubuntu/win |
| 06·MT-41 | Cache ＋/− | ja | P ✓ `test_render_cache`, `set_render_budget` | win |
| 06·MT-42 | Vorausladen wärmt an | ja | P ✓ `test_render_service` (Fake-CPU) | win |
| 06·MT-43 | Kleinste Fassung als Vorgabe | ja | P ✓ + V ✓ | win/ubuntu |
| 06·MT-44 | „Lesbarkeit geprüft" | ja | P ✓ | win |
| 06·MT-45 | Splitten übernimmt, Abbruch | ja | P ✓ (Cancel-Tokens) | win |
| 06·MT-46 | Fassungen bleiben erhalten | ja | P ✓ `test_variant_persistence` | win |
| 06·MT-47 | Roter Punkt bleibt weg | ja | P ✓ `test_status_and_nogain`, Beispieldatei | win |

### 07 Tastatur, Löschen, Sprache

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 07·MT-50 | Tastatur bewegen/tragen | ja | V ✓ | ubuntu |
| 07·MT-50b | Mehrere tragen | ja | V ✓ `App.moveresolver` | ubuntu |
| 07·MT-51 | Mehrere löschen | ja | V ✓; P ✓ `test_delete_many` | ubuntu/win |
| 07·MT-52 | Löschen mit Ordner (Rückfragen) | ja | V ✓ (Confirm-Stub) | ubuntu |
| 07·MT-53 | Umbenennen in der Zeile | ja | V ✓ `Tree.test` | ubuntu |
| 07·MT-54 | Sprache umschalten | ja | V ✓ `i18n.test`; Neustart-Merken G ○ | ubuntu |
| 07·MT-55 | Darstellung (Breite, Pfeile) | teilweise | V ✓ `useResizablePane`; Screenshot-Vergleich E ○ (Schriften unterscheiden sich je OS!); Rest: Optik | ubuntu / H |

### 08 Status, F2, Hilfe, Export, Sperre

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 08·MT-50 | Neue Einträge ohne Status | ja | P ✓ + V ✓ | win |
| 08·MT-51 | Status am Dokument | ja | P ✓ `test_status_*`; V ✓ | win/ubuntu |
| 08·MT-52 | Status am Ordner kaskadiert | ja | P ✓ | win |
| 08·MT-53 | Sammelpunkte, schwarzer Punkt | ja | V ✓ `status.test.js` | ubuntu |
| 08·MT-54 | Status bei Merge/Split | ja | P ✓ `test_split_merge` | win |
| 08·MT-55 | Roter Punkt vorn | ja | P ✓ + V ✓ | win/ubuntu |
| 08·MT-55b | Punkte verschwinden von selbst | ja | P ✓ + V (Sweep in App) ✓; Beispieldatei | win/ubuntu |
| 08·MT-56 | Umbenennen mit F2 | ja | V ✓ | ubuntu |
| 08·MT-57 | Hilfe, Flaggen, Meldelinks | ja | V ✓ `HelpModal`; Links: Aufruf-URL prüfen | ubuntu |
| 08·MT-58 | Exportoptionen | ja | V ✓ `ExportDialog`; P ✓ | win/ubuntu |
| 08·MT-59 | Dateisperre | ja | P ✓ `test_file_lock*` (zweiter Prozess, Windows-only) | win |

### 09 PDF-Tool

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 09·MT-50 | Im PDF-Tool öffnen, Ordner geht nicht | ja | P ✓ `open_node_in_pdftool`; V ✓ Menü | win/ubuntu |
| 09·MT-51 | Text hinzufügen, zurückspeichern | ja | E ○ (FreeText in PDF.js, laut CLAUDE.md offen) + P ✓ `SetNodeBytes` | ubuntu/win |
| 09·MT-52 | Text später weiterbearbeiten | ja | E ○ (Roundtrip als FreeText) | ubuntu |
| 09·MT-53 | Formularfeld ausfüllen/speichern | ja | E ✓ Feld rendert (`pdftool.spec`); Speichern-Roundtrip ○ | ubuntu |
| 09·MT-54 | Link öffnet Browser | teilweise | E ✓ `target=_blank`; G ○ Fenster bleibt; Rest: echter System-Browser | ubuntu / H |

### 10 DATEV

| ID | Titel | Auto? | Mechanismus | Runner |
|---|---|---|---|---|
| 10·MT-DATEV-01 | Modus ein/aus | ja | P ✓ `test_settings`; V ✓ `DatevBar`; „keine Verbindung" gegen geschlossenen Port D ○ | win |
| 10·MT-DATEV-02 | Kennzeichen bei Checkout | ja | P ✓ `test_datev_coreapi` (Fake-Service) | win |
| 10·MT-DATEV-03 | Geschütztes Zurückschreiben | teilweise | P ✓ + D ○ (Protokoll, Backup, lokales Mitspeichern); Rest: echtes DATEV (Änderungsdatum) | win / H |
| 10·MT-DATEV-04 | Konflikte verweigert | teilweise | P ✓ `test_datev_writeback` (reine Logik); D ○; Rest: echtes Auschecken durch Dritte | win / H |
| 10·MT-DATEV-05 | Ablegen (Dialog, Felder) | teilweise | E ✓ `datev-pdftool.spec`, V `datevFiling`; D ○; Rest: Felder (Jahr/Monat/Beleg) im echten DATEV prüfen (noch nicht live verifiziert, CLAUDE.md) | ubuntu/win / H |
| 10·MT-DATEV-06 | Export nach DATEV (auch aufgeteilt) | teilweise | P ✓ `datev_export` mit Fake-Service; D ○; Rest: echte Dokumente | win / H |
| 10·MT-DATEV-07 | Ausgeschaltet unsichtbar | ja | E ✓ (`DATEV mode off`), V ✓ | ubuntu |
| 10·MT-DATEV-08 | Checkout-PDF im PDF-Tool | teilweise | E ✓ `datev-pdftool.spec`; Scan-Rendering (JBIG2/wasm) E ○ mit Scan-Fixture; Rest: echter Checkout/Einchecken | ubuntu / H |
| 10·MT-DATEV-09 | PDF-Tool-Dokument ablegen | teilweise | E ✓ (Node-Binding file-anew); P ✓; D ○; Rest: DATEV live | ubuntu/win / H |

## Reihenfolge der Umsetzung (Vorschlag)

1. **Sofort:** `ci.yml` (dieser Commit) – P/V/E laufen bei jedem Push. Erster Lauf zeigt, ob LFS-Fixtures, Python-Matrix und Windows-Tests grün sind (nicht lokal verifizierbar, siehe unten).
2. **Danach:** G-Probelauf als eigener Workflow (`workflow_dispatch`): WebView2-Check, HKLM-Policy, `host.py` mit Launcher, Playwright `connectOverCDP`, ein Smoke-Test (Fenstertitel = Version, Datei öffnen, Umbenennen, Strg+S). Erst wenn stabil → nächtlich.
3. **Dann:** fehlende E-Specs (FreeText-Roundtrip, Zoom-Anker, Strg+Mausrad), Fake-DATEV (D), Office auf self-hosted (O).
4. **Manuelle Tests schrumpfen:** `manual_tests/` auf die ~12 menschlichen Prüfpunkte eindampfen, sobald G stabil läuft; Testkit-Generator bleibt (liefert die Eingabedateien).

## Nicht verifizierbar in dieser Umgebung (nur auf echtem Windows)

- Ob `windows-latest` eine nutzbare WebView2-Runtime und interaktive Sitzung hat (Quellenlage informell/widersprüchlich).
- Ob CDP bei erhöhtem Runner-Prozess mit HKLM-Policy zuverlässig verbindet (Runtime-Version driftet).
- `curl.exe --negotiate` gegen den lokalen Fake-Server (SSPI ohne Domäne).
- MSIX-Sideload mit Selbstsignatur auf dem Runner.
- Die tatsächliche Grünheit der Python-Suite auf `windows-latest` (hier Linux, LFS-Fixtures nur als Zeiger vorhanden).
- Aktionen sind auf **feste Hauptversionen** gepinnt, nicht auf Commit-SHA: die SHAs ließen sich hier nicht belastbar abrufen. Empfehlung: SHA-Pinning per Dependabot (`github-actions`-Ökosystem) nachziehen.
