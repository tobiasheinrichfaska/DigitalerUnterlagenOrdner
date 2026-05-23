# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\general stuff\CLAUDE.md`](../general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: Python/Tkinter (ttk). Version: **3.5.1**.

Entry point: `belegtool_main.py` — run with `python belegtool_main.py`.

---

## Architecture

### GUI layer

| File | Role |
|---|---|
| `belegtool_main.py` | Main window (TkinterDnD), menu bar, `_update_menu_states()`, update check |
| `panel_controls.py` | Toolbar (3 buttons), all action handlers (import, export, split, merge, …) |
| `view_tree.py` | TreeView frame, context menu, drag-and-drop, keyboard bindings |
| `view_preview.py` | Preview canvas, zoom, DPI slider, compression commit/reset, rotation |

### Data model

| File | Role |
|---|---|
| `pdf_node.py` | `PDFNode`: tree node (file/folder), compression, preview generation, split/merge/copy/delete |
| `pdf_storage.py` | `PDFStorage`: JSON serialization, export with TOC, .belegtool format |

### Import & Export

| File | Role |
|---|---|
| `universal_importer.py` | Multi-format import: PDF, images (jpg/png/webp/heic), Office (Word/Excel/PPT via COM), archives (ZIP/TAR), email (eml/msg) |
| `toc_export.py` | PDF export with printed TOC, clickable annotations (pikepdf), sidebar bookmarks, auto-split >100 pages |
| `compress_pdf_bytes.py` | Render-based compression (JPG/PNG), pikepdf structural compression, method comparison |

### Utilities

| File | Role |
|---|---|
| `tools.py` | PDF sanitization (repair broken objects) |
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.5.1) |
| `log_config.py` | Logging setup |
| `status_display.py` | Title bar status loop |
| `preview_page.py` | Helper class for preview pages |

---

## Dependencies (`requirements.txt` maintained in repo)

| Package | Purpose |
|---|---|
| `tkinterdnd2` | Drag-and-drop in TreeView |
| `PyMuPDF` (`fitz`) | PDF rendering to images |
| `Pillow` | Image processing; HEIC support via `pillow-heif` |
| `pikepdf` | Advanced PDF manipulation (annotations, outline/bookmarks) |
| `pypdf` | PDF read/write (base) |
| `reportlab` | Render TOC pages (Canvas) |
| `xhtml2pdf` | HTML-to-PDF |
| `extract-msg` | Parse Outlook MSG files |
| `pywin32` | Word/Excel/PPT conversion via COM |
| `pyinstaller` | Build tool |

---

## Features

### Import pipeline
- **PDF / .belegtool** → loaded directly as nodes
- **Images** (jpg, png, webp, heic) → converted to PDF
- **Office** (Word, Excel, PPT) → Win32-COM or GhostScript → PDF
- **Archives** (ZIP, TAR) → structure preserved, loaded recursively
- **Email** (eml, msg) → body + attachments extracted as tree structure

### Tree operations
Split, merge (with DPI conflict check), create folder, delete, rename, deep copy, drag-and-drop (Ctrl = copy), keyboard move (Ctrl+arrows)

### Preview & compression
- Lazy-generated, cached; DPI slider 50–300 DPI
- Multi-method: test JPG, PNG, pikepdf in parallel → pick best
- Commit button (replace original), reset button

### Status system (per node)
- `erfasst` — green
- `zu erfassen` — blue, highlighted
- `vorjahreswert` — red, highlighted

### Export
- Single PDF with table of contents (TOC), clickable links, sidebar bookmarks
- Auto-split at >100 pages with cross-references
- .belegtool format (metadata + ZIP)

---

## Build

### Prerequisites
- Python 3.12 in PATH
- `tkinterdnd2/tkdnd` directory at the path specified in `belegtool.spec`

### Build (clean venv, onedir)
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
Output: `dist\BelegTool\BelegTool.exe` + all DLLs/data in the same directory.

onedir is intentional — faster startup, no temp extraction.

### Run for development
```powershell
python belegtool_main.py
```

---

## Tests

Framework: `pytest`. Covered modules: `pdf_node`, `pdf_storage`, `view_tree`, `view_preview`, `panel_controls`. 32 test files in the project directory.

```powershell
pytest
```

---

## Versioning

Tags follow **semantic versioning** `vMAJOR.MINOR.PATCH` — see workspace CLAUDE.md for the full convention.
`VERSION` in `version_info.py` always matches the latest tag. Legacy tags `v3.02`–`v3.05` predate this convention.

Workflow for each stable milestone:
```powershell
# 1. bump version_info.py: VERSION = "X.Y.Z"
# 2. git commit -m "chore: bump version to X.Y.Z"
# 3. git tag vX.Y.Z
```

Fall back to a previous version: `git checkout v3.05`
List all versions: `git tag`

Current stable tag: **v3.5.1**

---

## Open / deferred items
- **Zammad integration** — deferred, not started yet

---

## UI conventions
- Style: Windows-native ttk ("faithful ttk"), no custom colors except status highlights
- Toolbar: 3 buttons — [Import] [Save] [Save as]
- Context menu order: optimized by frequency of use (see `view_tree.py`)
- `_update_menu_states()` in `belegtool_main.py` controls context-sensitive activation of all menu items
