# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

## Projektübersicht
Desktop-Anwendung zur hierarchischen Verwaltung, Vorschau und dem Export von PDF-Dokumenten und Belegen. Zielplattform: Windows. UI: Python/Tkinter (ttk). Version: **3.02**.

Einstiegspunkt: `belegtool_main.py` — starten mit `python belegtool_main.py`.

---

## Architektur

### GUI-Schicht

| Datei | Funktion |
|---|---|
| `belegtool_main.py` | Hauptfenster (TkinterDnD), Menüleiste, `_update_menu_states()`, Update-Check |
| `panel_controls.py` | Toolbar (3 Buttons), alle Action-Handler (Import, Export, Split, Merge, …) |
| `view_tree.py` | TreeView-Frame, Kontextmenü, Drag-Drop, Tastenbelegung |
| `view_preview.py` | Preview-Canvas, Zoom, DPI-Schieber, Kompression-Commit/Reset, Rotation |

### Datenmodell

| Datei | Funktion |
|---|---|
| `pdf_node.py` | `PDFNode`: Knoten (Datei/Ordner), Kompression, Vorschau-Generierung, Split/Merge/Copy/Delete |
| `pdf_storage.py` | `PDFStorage`: JSON-Serialisierung, Export mit TOC, .belegtool-Format |

### Import & Export

| Datei | Funktion |
|---|---|
| `universal_importer.py` | Multi-Format Import: PDF, Bilder (jpg/png/webp/heic), Office (Word/Excel/PPT via COM), Archive (ZIP/TAR), E-Mail (eml/msg) |
| `toc_export.py` | PDF-Export mit gedrucktem TOC, anklickbaren Annotationen (pikepdf), Sidebar-Lesezeichen, Auto-Split >100 Seiten |
| `compress_pdf_bytes.py` | Render-basierte Kompression (JPG/PNG), pikepdf-Strukturkompression, Methoden-Vergleich |

### Utilities

| Datei | Funktion |
|---|---|
| `tools.py` | PDF-Sanitierung (Reparatur defekter Objekte) |
| `version_info.py` | `APP_NAME`, `VERSION` (aktuell 3.02) |
| `log_config.py` | Logging-Setup |
| `status_display.py` | Titelzeilen-Status-Loop |
| `preview_page.py` | Hilfsklasse für Vorschau-Seiten |

---

## Abhängigkeiten (keine requirements.txt im Repo — `requirements.txt` gepflegt)

| Package | Zweck |
|---|---|
| `tkinterdnd2` | Drag-Drop im TreeView |
| `PyMuPDF` (`fitz`) | PDF-Rendering zu Bildern |
| `Pillow` | Image-Verarbeitung, HEIC-Support via `pillow-heif` |
| `pikepdf` | Erweiterte PDF-Manipulation (Annotationen, Outline/Bookmarks) |
| `pypdf` | PDF lesen/schreiben (Basis) |
| `reportlab` | TOC-Seiten rendern (Canvas) |
| `xhtml2pdf` | HTML-zu-PDF |
| `extract-msg` | Outlook-MSG-Dateien parsen |
| `pywin32` | Word/Excel/PPT-Konversion über COM |
| `pyinstaller` | Build-Tool |

---

## Features

### Import-Pipeline
- **PDF / .belegtool** → direkt als Knoten
- **Bilder** (jpg, png, webp, heic) → zu PDF konvertiert
- **Office** (Word, Excel, PPT) → Win32-COM oder GhostScript → PDF
- **Archive** (ZIP, TAR) → Struktur beibehalten, rekursiv geladen
- **E-Mail** (eml, msg) → Inhalte + Anhänge als Struktur extrahiert

### Baum-Operationen
Split, Merge (mit DPI-Konflikt-Check), Ordner anlegen, Löschen, Umbenennen, Copy (Deep), Drag-Drop (STRG = Copy), Tastatur-Move (Ctrl+Pfeile)

### Vorschau & Kompression
- Lazy-generiert, gecacht; DPI-Schieber 50–300 DPI
- Multi-Methode: JPG, PNG, pikepdf parallel testen → beste auswählen
- Commit-Button (Original ersetzen), Reset-Button

### Status-System (pro Knoten)
- `erfasst` (grün)
- `zu erfassen` (blau, hervorgehoben)
- `vorjahreswert` (rot, hervorgehoben)

### Export
- Einzel-PDF mit Inhaltsverzeichnis (TOC), anklickbaren Links, Sidebar-Lesezeichen
- Auto-Split bei >100 Seiten mit Querverweisen
- .belegtool-Format (Metadaten + ZIP)

---

## Build

### Voraussetzungen
- Python 3.12 im PATH
- `tkinterdnd2/tkdnd`-Verzeichnis am in `belegtool.spec` hinterlegten Pfad

### Build ausführen (clean venv, onedir)
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
Ergebnis: `dist\BelegTool\BelegTool.exe` + alle DLLs/Daten im selben Verzeichnis.

**Kein onefile-Build** — onedir startet schneller (kein Entpacken in tmp).

### Manuell starten (Entwicklung)
```powershell
python belegtool_main.py
```

---

## Tests
Framework: `pytest`. Abgedeckte Module: `pdf_node`, `pdf_storage`, `view_tree`, `view_preview`, `panel_controls`. Tests liegen im Projektverzeichnis (32 Test-Dateien). Ausführen:
```powershell
pytest
```

---

## Offene Punkte / Bekannte TODOs
- **Zammad-Integration** — zurückgestellt, noch nicht begonnen
- CLAUDE.md laufend aktualisieren bei größeren Änderungen

---

## Wichtige Konventionen
- UI-Style: Windows-native ttk ("faithful ttk"), keine custom Farben außer Status-Highlights
- Toolbar: 3 Buttons — [Importieren] [Speichern] [Speichern als]
- Kontextmenü-Reihenfolge: optimiert nach Häufigkeit (siehe `view_tree.py`)
- `_update_menu_states()` in `belegtool_main.py` steuert kontextsensitive Aktivierung aller Menüeinträge
