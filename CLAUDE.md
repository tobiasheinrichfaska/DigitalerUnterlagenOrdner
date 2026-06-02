# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: Python/Tkinter (ttk). Version: **3.5.3**.

Entry point: `belegtool_main.py` — run with `python belegtool_main.py`.

---

## Architecture

### GUI layer

| File | Role |
|---|---|
| `belegtool_main.py` | Main window (TkinterDnD), menu bar, `_update_menu_states()` |
| `panel_controls.py` | Toolbar (3 buttons), all action handlers (import, export, split, merge, …) |
| `view_tree.py` | TreeView frame, context menu, drag-and-drop, keyboard bindings |
| `view_preview.py` | Preview canvas, zoom, DPI slider, compression commit/reset, rotation |

### Data model

| File | Role |
|---|---|
| `pdf_node.py` | `PDFNode`: tree node (file/folder), compression, preview (rendering delegated to `services/render`), split/merge/copy/delete. **No Tk** — uses the `progress`/`tasks` ports |
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
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.5.3) |
| `log_config.py` | Logging setup |
| `status_display.py` | Title bar status loop (Tk; **app layer only**) |
| `preview_page.py` | Preview page holder (PIL only — no Tk) |

### Headless core layer & ports (GUI-decoupled)

The domain model and processing modules import **no `tkinter`** — the GUI toolkit
lives only in the app layer (`belegtool_main`, `view_*`, `panel_controls`,
`status_display`, `test_mode`). This is Phase 1 of the React migration; see
[`docs/REACT_MIGRATION_PLAN.md`](docs/REACT_MIGRATION_PLAN.md) (on the
`react-migration` branch).

| File | Role |
|---|---|
| `services/render.py` | **Headless** PDF→preview rendering: `render_pdf_to_images` (PIL, for the Tk canvas) and `render_pdf_to_pngs` (PNG bytes, for a web UI). `PDFNode._create_previews` delegates here. |
| `progress.py` | Progress **port**: the core signals background-task start/finish (`task_started`/`task_finished`); the app installs a reporter forwarding to `status_display`. No-op by default. |
| `tasks.py` | Execution **port**: `submit(fn)` (swappable executor — daemon thread by default, pool/sync later) and `run_on_ui_thread(fn)` (UI-thread dispatch; inline when headless). |

Ports are installed by the GUI in `belegtool_main` (`progress.set_reporter`,
`tasks.set_ui_dispatcher`); a future backend installs its own implementations.

### Data-driven core (`core/`)

A separate, immutable, fully data-driven model (no Tk, no threads) — the basis
for the core service + React UI. **Reference: [`docs/data-model.html`](docs/data-model.html)**
(entities, commands, ER map) and [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

| File | Role |
|---|---|
| `core/model.py` | Immutable `Node`/`Document` value types + pure tree transforms (structural sharing) + serialization |
| `core/commands.py` | Frozen command data + pure reducer `apply(doc, cmd, engine=None)` (structural + engine-backed) |
| `core/engine.py` | `Engine` port (compress/rotate/split/merge/page_count) + `RealEngine` |
| `core/session.py` | `DocumentSession`: undo/redo + event log (replay invariant) |
| `core/bridge.py` | Convert ↔ `PDFStorage`/`.belegtool` (load/save real files into the model) |
| `core/server.py`, `pipe.py`, `protocol.py`, `client.py`, `cli.py` | Per-user named-pipe **core service** (Step 0a): multi-client handshake/open |

Covered by `tests/test_model.py`, `test_commands.py`, `test_engine_commands.py`,
`test_split_merge.py`, `test_session.py`, `test_bridge.py`, `test_core_*.py`.

### React UI + pywebview host (the new front end)

A **single warm Python process** ([`host.py`](host.py)) embeds the data-driven core
in-process and exposes it to a **React + Vite SPA** (`webui/`) over the pywebview
JS bridge (`window.pywebview.api.*`). No pipe/server in the active path; npm is
build-time only (the prod build is static assets under `webui/dist/`).

| File | Role |
|---|---|
| `host.py` | pywebview host: one shared `CoreApi`, one `HostApi` **per window** (bound to the window uid; stores the uid, never the window object — that recurses). Native dialogs, `new_window`, per-window close guard (`window.__belegDirty` via `evaluate_js`), startup `_prewarm` of the heavy PDF libs. |
| `core/api.py` | `CoreApi` façade (JSON in/out, one `DocumentSession` per window): `open/save/dispatch/undo/redo/render/render_compressed/compress_options/import_paths/import_bytes/export/config/any_dirty`. Per-session `dirty` tracking. |
| `webui/src/App.jsx` | Main component: toolbar (open/import/save/export/new-window/undo/redo), tree + preview panes, OS file-drop, keyboard shortcuts, dirty/notice state |
| `webui/src/Tree.jsx` | Tree view + all drag-drop: internal move (into/before/after, slide-to-level ghost) **and** OS file import sharing the same zones |
| `webui/src/PreviewControls.jsx` | Lazy working-preview compression (method dropdown loads on open → "Kompression läuft", apply via "Lesbarkeit geprüft"), rotate |
| `webui/src/ContextMenu.jsx`, `core.js` | Right-click ops (incl. Merge→1 PDF / In neuen Ordner); thin `window.pywebview.api` wrapper |

**Run:** dev — `cd webui && npm run dev` then `set BELEG_DEV=1 && python host.py`;
prod — `cd webui && npm run build` then `python host.py`. **Manual tests:**
[`manual_tests/05_react_ui.md`](manual_tests/05_react_ui.md).

Performance notes worth keeping: `.belegtool` is parsed **once** on load (was
re-parsed per node); `universal_importer` (win32com/COM, ~2.6 s) is imported lazily
only when an Office/archive/email import needs it; `host._prewarm` warms the
render/compress path at startup.

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
- Multi-method: test JPG, PNG, pikepdf in parallel → pick best; methods larger than original are hidden from the dropdown
- Original file size shown in labels for comparison
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
Output: `dist\PDF-Storage\PDF-Storage.exe` + all DLLs/data in the same directory.

onedir is intentional — faster startup, no temp extraction.

### Run for development
```powershell
python belegtool_main.py
```

---

## Tests

Framework: `pytest`. ~50 test files in `tests/` cover the legacy modules (`pdf_node`, `pdf_storage`, `view_tree`, `view_preview`, `panel_controls`) **and** the data-driven `core/` (model, commands, engine, session, bridge, api, ipc) plus the pywebview host glue (`test_host.py`). Run `pytest` for the current pass count.

```powershell
pytest
```

PDF test fixtures live in `tests/data/input/` and are generated by
`python tests/make_fixtures.py` (deterministic, compressible). Golden-master
references are in `tests/data/expected/`.

### Manual tests (human tester)

Step-by-step manual test instructions for a non-developer live in
[`manual_tests/`](manual_tests/README.md) — import, tree operations, preview/
compression, export, persistence, and the in-app Test mode. Keep them current
when user-facing flows change (workspace convention).

---

## Versioning

Tags follow **semantic versioning** `vMAJOR.MINOR.PATCH` — see workspace CLAUDE.md for the full convention.
`VERSION` in `version_info.py` always matches the latest tag. Legacy tags `v3.02`–`v3.05` predate this convention.

Workflow for each stable milestone:
```powershell
# 1. bump version_info.py: VERSION = "X.Y.Z"
# 2. git commit -m "chore: bump version to X.Y.Z"
# 3. git tag vX.Y.Z
# 4. git push origin master --tags
```

Push to GitHub regularly — at the end of every meaningful session, not just on version bumps. Remote: `https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner.git`

Fall back to a previous version: `git checkout v3.05`
List all versions: `git tag`

Current stable tag: **v3.5.3**

---

## Open / deferred items
- **Zammad integration** — deferred, not started yet
- **GUI test harness — Tk root churn (deferred)**: `tests/test_ui_lockout.py`
  creates a fresh `tk.Tk()` per test (see the `preview` fixture). Running *that
  file alone in a tight loop* intermittently fails Tk init
  (`couldn't read … panedwindow.tcl`). A shared module/session root was tried and
  **regressed the full suite** — leaked `after`-poll timers from one test fire
  against the next test's destroyed frame (`TclError`). Per-test root is reliable
  in normal/full runs (119 passed, 0 failed). A proper fix needs one
  session-wide root for *all* GUI tests **plus** strict per-test `after`-timer
  cancellation — a real refactor, not a quick win. Low priority (isolation-only).

---

## UI conventions
- Style: Windows-native ttk ("faithful ttk"), no custom colors except status highlights
- Toolbar: 3 buttons — [Import] [Save] [Save as]
- Context menu order: optimized by frequency of use (see `view_tree.py`)
- `_update_menu_states()` in `belegtool_main.py` controls context-sensitive activation of all menu items
