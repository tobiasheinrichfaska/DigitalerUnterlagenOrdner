# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: **React + Vite SPA inside a pywebview host** (Edge WebView2). Version: **3.6.0**.

Entry point: **`host.py`** — the single pywebview host. `python host.py` launches
the GUI; `python host.py <file.belegtool>` opens that file on startup.

> **v3.6.0 removed the legacy Tk GUI** and the dual `app.py` entry point. The only
> front end is now the React/pywebview GUI; `host.py` is the sole entry. Removed
> files: `app.py`, `launch_util.py`, `belegtool_main.py`, `panel_controls.py`,
> `view_tree.py`, `view_preview.py`, `status_display.py`, `test_mode.py` (and their
> tests). `tkinterdnd2` is gone from `requirements.txt`.

---

## Architecture

### Entry point & host

| File | Role |
|---|---|
| `host.py` | **The single entry point.** pywebview host: one shared `CoreApi`, one `HostApi` **per window** (bound to the window uid). Native dialogs, `new_window`, per-window close guard (`window.__belegDirty`), startup `_prewarm` of the heavy PDF libs. |

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
| `testmode.py` | **Testmodus** headless data layer: runs the golden-master ops (compression/split/merge) and returns INPUT/LIVE/EXPECTED PDF bytes + status. Pure; `CoreApi.test_mode` renders thumbnails, the React `TestMode` view displays them (toolbar 🧪). |
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.6.0) |
| `log_config.py` | Logging setup |
| `preview_page.py` | Preview page holder (PIL only). Now used only by the data model's eager-preview path — a candidate for removal in a future data-model cleanup. |

### Headless core layer & ports (GUI-decoupled)

The domain model and processing modules import **no `tkinter`**. With the legacy
Tk GUI removed (v3.6.0), the only UI is the React/pywebview host; the React
migration that this decoupling enabled is effectively complete.

| File | Role |
|---|---|
| `services/render.py` | **Headless** render: `render_pdf_to_images` (PIL), `render_pdf_to_pngs` (PNG bytes for the SPA), and the windowed-cache primitives `render_page` (single page), `page_count`, `page_dims`. |
| `core/render_policy.py` | **Pure** prefetch policy: `predict_window`, `next_fill_target`/`fill_order`. No rendering/threads/UI — the brain of the (in-progress) windowed render cache. |
| `progress.py` | Progress **port**: the core signals background-task start/finish (`task_started`/`task_finished`); the app may install a reporter forwarding to its UI. No-op by default. |
| `tasks.py` | Execution **port**: `submit(fn)` (swappable executor — daemon thread by default, pool/sync later) and `run_on_ui_thread(fn)` (UI-thread dispatch; inline when headless). |

Ports default to a no-op reporter and a daemon-thread executor; the host can
install its own implementations (`progress.set_reporter`, `tasks.set_ui_dispatcher`)
if it needs to surface progress or marshal onto a UI thread.

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
prod — `cd webui && npm run build` then `python host.py`. **Unit tests:** `cd webui
&& npm test` (Vitest + jsdom; `src/core.test.js` smoke-tests the `core.js` bridge —
method-name mapping and the `pywebviewready` wait/fail-fast). **Manual tests:**
[`manual_tests/05_react_ui.md`](manual_tests/05_react_ui.md).

Performance notes worth keeping: `.belegtool` is parsed **once** on load (was
re-parsed per node); `universal_importer` (win32com/COM, ~2.6 s) is imported lazily
only when an Office/archive/email import needs it; `host._prewarm` warms the
render/compress path at startup.

---

## Dependencies (`requirements.txt` maintained in repo)

| Package | Purpose |
|---|---|
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
- Multi-method: test JPG (grayscale), **JPG color (`jpg_color`)**, PNG (grayscale),
  pikepdf (structural, color preserved) in parallel → pick smallest; methods larger
  than original are hidden from the dropdown. `jpg_color` keeps color so color
  documents aren't silently desaturated; readable labels live in `PreviewControls.jsx`
  (`METHOD_LABELS`).
- Original file size shown in labels for comparison
- Commit button (replace original), reset button

### Status system (per node)
- `erfasst` — green
- `zu erfassen` — blue, highlighted
- `vorjahreswert` — red, highlighted

### Export
- Single PDF with table of contents (TOC), clickable links, sidebar bookmarks
- Auto-split at >100 pages with cross-references
- `.belegtool` format: a single PDF whose pages are the nodes' **effective bytes**
  (`current_pdf_data`), with the tree serialized into the `/JSONStructure` metadata
  key. Import gates the (expensive) structure parse on a cheap `b"/JSONStructure"`
  byte check.

### Persistence / save policy (v3.6.0)
The file stores **only `current_pdf_data` per node** — never a separate original.
So a **committed** node ("Lesbarkeit geprüft" = a `Compress` was applied) saves only
its compressed result; its source is **dropped on save** (the file is never 2×).
On reload (headless/core path) a committed node comes back **coherently**:
`current_data = bytes, original_data = None, is_compressed = True`. Consequences,
enforced in the logic layer and surfaced to the UI via `has_source` in `Node.to_dict`:
- **Re-compress is blocked** — `Compress` guards on `original_data` (no double compression).
- **Reset is blocked** — nothing to revert to (`_reset` raises `CommandError`).
- The compression dropdown shows **"bereits komprimiert (keine Quelle)"**, disabled.
- ⚠ **Irreversible:** the source is gone for committed nodes — see `manual_tests` MT-17.
Uncommitted nodes keep their source and stay fully editable.

---

## Build

### Prerequisites
- Python 3.12 in PATH
- Node.js (the build runs `npm run build` in `webui/` first)

### Build (clean venv, onedir) — single React/pywebview exe
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```
Output: `dist\BelegTool\BelegTool.exe` + all DLLs/data in the same directory.
`build.ps1` builds `webui/dist` (Vite) before PyInstaller; the spec
([`belegtool.spec`](belegtool.spec)) has **`host.py`** as its single Analysis
entry and bundles the React assets plus the pywebview + pythonnet/clr (Edge
WebView2) stack. onedir is intentional — faster startup, no temp extraction.

| Command | GUI |
|---|---|
| `BelegTool.exe` | React/pywebview GUI |
| `BelegTool.exe <file.belegtool>` | React/pywebview GUI, opening that file |

### Run for development
```powershell
cd webui && npm run build   # build the SPA once (or `npm run dev` + BELEG_DEV=1)
python host.py              # launch the GUI
python host.py file.belegtool   # …opening a file
```

---

## Tests

Framework: `pytest`. Tests in `tests/` cover the data model (`pdf_node`, `pdf_storage`), compression/import, the data-driven `core/` (model, commands, engine, session, bridge, api, ipc, **render_policy**), the render helpers, and the pywebview host glue (`test_host.py`). Run `pytest` for the current pass count.

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

Current stable tag: **v3.6.0**

---

## Open / deferred items
- **Manual tests 01–04 still describe legacy Tk flows** — after the v3.6.0 Tk
  removal, their step wording (menus, toolbar) is stale; re-verify/rewrite each
  against the React UI. The features themselves are unchanged.
- **Dead Tk-preview path in the data model** — `PDFNode` still carries the eager
  PIL-preview / `compress_lazy` / `PreviewPage` machinery (the `generate_previews=True`
  branch) that only the removed Tk GUI used. The headless React path never calls it.
  Safe to keep, but a candidate for a focused data-model cleanup (would also drop
  `preview_page.py` and the background-compress-on-import threads the tests still trip on).
- **Headless import is now bytes-only end to end** — plain-PDF *and* archive/email
  paths honor `generate_previews=False` (`from_recursive_array`/`_from_structure_entry`
  thread the flag); page count uses `fitz.page_count`; the `/JSONStructure` metadata
  parse is gated on a cheap `b"/JSONStructure" in data` byte check (the marker
  survives pikepdf's compress+linearize, so `.belegtool`/structured-PDF imports are
  still honored — locked by `test_structured_pdf_import_honors_json`). Warm import is
  ~1 ms; the remaining cold-open cost is Windows Defender scanning the file, outside
  our control.
- **Windowed render cache (designed, not built)** — see the design discussion: render
  only a page window on demand (±5 prefetch), pure `predict_window`/`next_fill_target`
  policy functions in the core, a stateful `RenderService` (200 MiB global LRU,
  per-node `version` invalidation, CPU-headroom-throttled background filler) in an
  application/service layer between the pure model and the UI. Today `CoreApi.render`
  rasterizes **all** pages into one base64 blob (~28 s + 157 MiB for a 200-page file).
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
- React + Vite SPA in `webui/`; rendered inside the pywebview host
- Toolbar: open/import/save/export/new-window/undo/redo ([`App.jsx`](webui/src/App.jsx))
- Tree + drag-and-drop in [`Tree.jsx`](webui/src/Tree.jsx); right-click ops in [`ContextMenu.jsx`](webui/src/ContextMenu.jsx)
- Compression controls (method dropdown incl. `jpg_color`, DPI, apply/reset) in [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)
