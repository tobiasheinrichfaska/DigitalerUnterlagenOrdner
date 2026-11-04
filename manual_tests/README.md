# Manuelle Tests – BelegTool (Digitaler Unterlagen-Ordner)

Schritt-für-Schritt-Anleitungen, mit denen eine Testperson **ohne Programmierkenntnisse** BelegTool von Hand prüft. Sie ergänzen die automatischen Tests um das, was nur ein Mensch am Bildschirm beurteilen kann: Vorschau, Ziehen mit der Maus, Dialoge, exportierte Dateien.

## Was Sie brauchen

- Einen Windows-PC (Windows 11 oder Windows 10) mit installiertem BelegTool – die Installation beschreibt `00_Installation_Microsoft_Store.pdf`.
- Dieses Testpaket (den Ordner `testpakete`).
- Nur für einzelne Tests: installiertes **Microsoft Office** (Import von Word, Excel, PowerPoint) und einen **DATEV-Arbeitsplatz** (Bereich 10).

## So ist das Testpaket aufgebaut

Jeder Bereich hat einen Ordner, jeder Test darin einen eigenen Unterordner. Dort liegen die **Anleitung als PDF** und – wenn der Test Dateien braucht – der Ordner **Beispieldateien**.

```
testpakete
├─ 00_Start_hier.pdf                        (dieses Dokument)
├─ 00_Installation_Microsoft_Store.pdf
├─ 01_import
│  ├─ MT-01_Einzelnes-PDF-importieren
│  │  ├─ 01_MT-01_Einzelnes-PDF-importieren.pdf     (Anleitung)
│  │  └─ Beispieldateien
│  │     └─ Rechnung_5_Seiten.pdf
│  └─ …
└─ 02_tree_operations
   └─ …
```

Alle Beispieldateien sind frei erfunden und enthalten keine echten Personen- oder Firmendaten.

## So gehen Sie vor

1. **Version notieren.** Sie steht in der Titelleiste des BelegTool-Fensters, z. B. „DigitalerUnterlagenOrdner 3.11.4“.
2. **Einen Test auswählen.** Die Reihenfolge der Bereiche ist eine Empfehlung; jeder Test lässt sich für sich durchführen.
3. **Den Ordner „Beispieldateien“ des Tests an einen Arbeitsort kopieren**, etwa auf den Desktop. Viele Tests verändern und speichern Dateien – so bleibt das Original im Testpaket unberührt und der Test lässt sich wiederholen.
4. **Die Schritte der Reihe nach ausführen** und das Ergebnis mit dem Abschnitt „Erwartetes Ergebnis“ vergleichen. Achten Sie auf die Vermerke *Nicht offensichtlich* – sie beschreiben Verhalten, das überraschen kann, aber gewollt ist.
5. **Das Testprotokoll** am Ende der Anleitung ausfüllen und Abweichungen melden.

## Das Fenster von BelegTool

Oben liegt die **Symbolleiste**, links der **Baum** mit Ordnern und Dokumenten, rechts die **Vorschau**, unten die **Statusleiste**. Die meisten Aktionen an einem Eintrag erreichen Sie über das **Kontextmenü (Rechtsklick)**; eine Menüleiste gibt es nicht.

| Symbol | Name | Aufgabe |
|---|---|---|
| 📂 | Öffnen | eine `.belegtool`- oder PDF-Datei öffnen |
| 🗗 | Neues Fenster | ein weiteres Dokument in einem eigenen Fenster |
| 📥 | Importieren | Dateien in das geöffnete Dokument holen |
| 💾 und ▾ | Speichern / Speichern unter… | speichern; der Pfeil öffnet „Speichern unter…“ |
| ⬇ | Export PDF | als ein PDF mit Inhaltsverzeichnis exportieren |
| ＋ | Ordner | einen neuen Ordner anlegen |
| ↶ ↷ | Rückgängig / Wiederholen | den letzten Schritt zurücknehmen oder wiederherstellen |
| 🏷️ | Tags | Schlagwörter ein- und ausschalten |
| 🌐 | Sprache | die Sprache der Oberfläche wählen |
| ❓ | Hilfe | Kurzanleitung im Programm |
| DATEV | DATEV-Modus | nur für Kanzlei-Arbeitsplätze mit DATEV |

Seit Version 3.10.0 zeigt die Symbolleiste **nur Symbole**; der Name erscheint als Hinweistext, wenn der Mauszeiger auf dem Symbol ruht. In den Anleitungen stehen Symbol und Name zusammen, z. B. **📥 Importieren**.

## Begriffe

- **Eintrag** – eine Zeile im Baum: ein **Dokument** (hat Seiten) oder ein **Ordner** (enthält Einträge).
- **„•“** neben 💾 und hinter dem Titel – es gibt ungespeicherte Änderungen.
- **Roter Punkt vorn** in einer Zeile – über die Komprimierung dieses Dokuments ist noch nicht entschieden.
- **Punkte am Zeilenende** – der Status: gelb = Zu erfassen, grün = Erfasst, rot = Vorjahr.

## Welche Version beschreiben die Anleitungen?

In der Fußzeile jeder Anleitung steht die Version, für die sie geschrieben wurde. Der Microsoft Store liefert die zuletzt dort veröffentlichte Version – sie kann **älter** sein. Tests mit dem Vermerk **„erst ab Version … testbar“** setzen mindestens diese Version voraus; kreuzen Sie sie mit einer älteren Version bitte als „Nicht durchführbar“ an.

## Bitte nicht als Fehler melden

- **Komprimierung ist nach dem Speichern nicht umkehrbar.** Ein übernommenes Dokument („Lesbarkeit geprüft“) verliert beim Speichern seine Quelle und zeigt danach „bereits komprimiert (keine Quelle)“. Das ist gewollt.
- **Getarnte Datei direkt importiert** (Bereich 01, MT-05, Schritt 1): In Version 3.11.4 entsteht ein leerer Eintrag statt einer Ablehnung. Die Abweichung ist bekannt.
- **Mehrseitige TIFF-Bilder:** Es wird nur die erste Seite übernommen. Bekannte Einschränkung.

## Abweichungen melden

Bitte melden Sie jede Abweichung unter https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/issues – mit

- **Bereich und Test-ID** (z. B. „07 · MT-52“; die ID allein reicht nicht, weil manche Nummern in mehreren Bereichen vorkommen),
- der **getesteten Version**,
- dem **Schritt**, bei dem es abwich, und dem, was Sie stattdessen gesehen haben – gern mit Bildschirmfoto.

<!-- testkit:entwickler -->

## Pflege (für Entwickler)

Die Markdown-Dateien in diesem Ordner sind die **einzige Quelle**. Die PDFs und Beispieldateien unter `testpakete/` werden daraus erzeugt und nie von Hand bearbeitet:

```
.build_venv\Scripts\python.exe scripts\build_testkit.py            # Beispieldateien + alle PDFs
.build_venv\Scripts\python.exe scripts\build_testkit.py --check    # nur die Quellen prüfen
```

Der PDF-Druck läuft über Microsoft Edge (headless). Der Ordner `testpakete/` gehört dem Skript: Dateien, die es nicht selbst geschrieben hat, entfernt es.

**Format eines Testfalls** (ausgewertet von `scripts/testkit/cases.py`):

```
## MT-01: Titel

**Ab Version:** 3.10.0                       (optional)

**Beispieldateien:** `a.pdf`, `b.zip`        (optional; Namen aus scripts/testkit/samples.py)

**Voraussetzungen:** …

**Schritte:**
1. …

**Erwartet:**
- …

**Hinweis:** …                               (optional)
```

„Schritte“ und „Erwartet“ dürfen mehrfach vorkommen und einen Zusatz in Klammern tragen, z. B. `**Schritte (A – Ordner zuklappen):**`. Eine neue Beispieldatei ist eine Zeile im Katalog von `samples.py`.

Wenn sich ein sichtbarer Ablauf im Programm ändert, gehört die Anpassung des Testfalls und das Neuerzeugen des Testpakets in dieselbe Sitzung.

| Datei | Bereich |
|---|---|
| [00_installation.md](00_installation.md) | Installation aus dem Microsoft Store, Version, Deinstallation |
| [01_import.md](01_import.md) | Import: PDF, BelegTool-Dokument, Bilder, E-Mail, Text/HTML, Office, Archive, Sicherheitsprüfung |
| [02_tree_operations.md](02_tree_operations.md) | Splitten, Zusammenführen, Ordner, Mehrfachauswahl, Verschieben, Rückgängig |
| [03_preview_and_compression.md](03_preview_and_compression.md) | Vorschau, Zoom, Komprimierung, Drehen, Status-Punkte |
| [04_export_persistence.md](04_export_persistence.md) | Export, Speichern/Öffnen, Dateizuordnung, verworfene Quelle, Speichern-Dialog |
| [05_react_ui.md](05_react_ui.md) | Bedienoberfläche: Start, Ziehen, mehrere Fenster, Tastenkürzel, große PDFs, Tags |
| [06_status_cache_compression.md](06_status_cache_compression.md) | Statusleiste, Vorschau-Cache, Komprimierungsablauf |
| [07_keyboard_delete_language.md](07_keyboard_delete_language.md) | Tastatur, Löschen mit Rückfragen, Umbenennen, Sprache, Darstellung |
| [08_status_dots_help.md](08_status_dots_help.md) | Status-Regeln, roter Punkt, F2, Hilfe, Exportoptionen, Dateisperre |
| [09_pdf_tool.md](09_pdf_tool.md) | PDF-Tool: Text hinzufügen, Formulare ausfüllen |
| [10_datev.md](10_datev.md) | DATEV-Modus – **braucht einen DATEV-Arbeitsplatz** |

**Bekannt:** Die Test-IDs sind nur **innerhalb eines Bereichs** eindeutig (z. B. gibt es MT-50 in den Bereichen 07, 08 und 09). Die PDF-Namen tragen deshalb die Bereichsnummer.
