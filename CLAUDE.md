# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: **React + Vite SPA inside a pywebview host** (Edge WebView2). Version: **3.7.0**.

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
| `pdf_node.py` | `PDFNode`: serialization carrier for the `.belegtool` I/O path only (bytes + metadata, `to_dict`/`from_recursive_array`/`copy`). **No rendering, no operations** — split/merge/rotate/compress live in `core/engine` |
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
| `tools.py` | `sanitize_pdf`: repair broken PDFs (xref/object streams) via pikepdf — a no-op on readable files. Wired into `PDFStorage._load_pdf`'s plain-PDF branch (never the `.belegtool` path). |
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.7.0) |
| `log_config.py` | Logging setup |
| `preview_page.py` | Preview page holder (PIL only). Now used only by the data model's eager-preview path — a candidate for removal in a future data-model cleanup. |

### Headless core layer & ports (GUI-decoupled)

The domain model and processing modules import **no `tkinter`**. With the legacy
Tk GUI removed (v3.6.0), the only UI is the React/pywebview host; the React
migration that this decoupling enabled is effectively complete.

| File | Role |
|---|---|
| `services/render.py` | **Headless** render: `render_pdf_to_images` (PIL), `render_pdf_to_pngs` (PNG bytes for the SPA), and the windowed-cache primitives `render_page` (single page), `page_count`, `page_dims`. |
| `core/render_policy.py` | **Pure** prefetch policy: `predict_window`, `next_fill_target`/`fill_order`. No rendering/threads/UI — the brain of the windowed render cache. |
| `services/render_service.py` | **Stateful** `RenderService` + `RenderCache`: global 200 MiB LRU keyed `(node, version, page, dpi)`, generation token, CPU-throttled background filler that warms **up to `max_workers` pages at once** on a below-normal-priority thread pool. Rendering + CPU reading are injected (testable with fakes). `CoreApi` owns one instance; `render_window`/`page_count`/`page_dims` use it (version = `crc32` of the effective bytes → auto-invalidates on edit). |
| `services/cpu.py` | **CPU-fairness primitives** for the background pools: `worker_count` (capped 4 local / 2 RDP, `BELEG_WORKERS` override), `set_current_thread_below_normal` (so background work yields to interactive/other sessions), `SystemCpuSampler` (`GetSystemTimes`, no extra dep → prefetch backs off under load), `is_remote_session`. Pure/injected → unit-tested headless. ⚠ Thread parallelism is **GIL-limited** for PyMuPDF rasterization (~1.2× on 4 workers); its real value is fairness + foreground preemption, not raw throughput (true multicore would need processes — see Open items). |
| `tasks.py` | Execution **port**: `submit(fn)` (swappable executor — daemon thread by default, pool/sync later) and `run_on_ui_thread(fn)` (UI-thread dispatch; inline when headless). Used by `universal_importer`. |

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
Split, merge (with DPI conflict check), create folder, delete, rename, deep copy, drag-and-drop.

**Keyboard structuring** (`webui/src/treeNav.js` pure helpers + `App.jsx` `onKey`):
↑/↓ navigate the visible rows; ←/→ collapse/expand a folder (or step out/in).
**Insert** grabs the selected node (dashed outline); while grabbed, arrows move it
**optically** (↑/↓ reorder, → nest into the folder above, ← out a level) — nothing is
committed until **Insert** drops it (a single undoable `Move`); **Esc** cancels and
reverts. (Ctrl is multi-select, so it can't be the move modifier.)

**Folder collapse** is a **persisted** `Node.collapsed` field (set via `SetCollapsed`
/ `SetAllCollapsed` commands — undoable, marks dirty, round-trips in `.belegtool`).
Chevron in the tree, ←/→ keys, and context-menu **Aufklappen/Zuklappen** + **Alle
auf-/zuklappen**. Cuts scrolling on large trees.

### Preview & compression
- Lazy-generated, cached; DPI slider 50–300 DPI
- Multi-method: test JPG (grayscale), **JPG color (`jpg_color`)**, PNG (grayscale),
  pikepdf (structural, color preserved) in parallel → pick smallest; methods larger
  than original are hidden from the dropdown. `jpg_color` keeps color so color
  documents aren't silently desaturated; readable labels live in `PreviewControls.jsx`
  (`METHOD_LABELS`).
- Original file size shown in labels for comparison — incl. the size of the
  "unkomprimierte Fassung" entry itself (from `compress_options.original_size`)
- Commit button (replace original), reset button
- The preview zoom bar shows the windowed viewport's page position (**"Seite n / m"**,
  reported up from `Preview.jsx`), falling back to the node's total page count
- **Split parts are compressible:** `Split`/`SplitInto` parts carry the *uncompressed
  source* pages, so they are no longer flagged `no_compression`. ⚠ Parts in
  already-saved `.belegtool` files keep the old flag until re-split.

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

**Persisted compression variants (Option A).** Computed-but-not-applied variants are
embedded in the `.belegtool` so reopening doesn't recompute (the 6–9 s sweep). Each
node's variants are a **PDF attachment keyed by node id** (`variant_<id>`) — not pages,
not tree nodes; ignored by plain viewers. `CoreApi.save` calls
[`services/variant_store.embed_variants`](services/variant_store.py) (packs
`{dpi:{method:bytes}}` via [`variant_blobs`](services/variant_blobs.py) ↔ a stored ZIP,
no pickle); `open` calls `seed_variants_from_file` → `RealEngine.seed_variants` (an
unbounded **persisted** layer next to the LRU memo). For id-keyed blocks to match on
reload, the node **`uid` is now persisted** in `/JSONStructure` (`to_dict`/`_parse_node`).
This does **not** reverse drop-source-on-save: only nodes that *still have a source*
(uncommitted) store variants; a committed node has none. Per-file variant budget caps
the bloat. ⚠ Variants live in the file → it grows; not a separate sidecar.

---

## Build

### Prerequisites
- Python 3.12 in PATH
- Node.js (the build runs `npm run build` in `webui/` first)
- App icon: source `assets/icon.svg`; the exe icon is `assets/icon.ico` (multi-size,
  generated from the SVG; `belegtool.spec` sets `EXE(icon=…)`). The same artwork is
  the web favicon (`webui/public/favicon.svg`). Regenerate the `.ico` from the SVG if
  the artwork changes.

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

Framework: `pytest`. Tests in `tests/` cover the `.belegtool` carrier (`pdf_storage`, the `pdf_node` round-trip), compression/import (incl. `test_compress_parallel` — content+order match of the multi-worker path), the data-driven `core/` (model, commands, engine, session, bridge, api, ipc, **render_policy**), the render helpers, the CPU-fairness primitives (`test_cpu`), and the pywebview host glue (`test_host.py`). The legacy PDFNode-operation/eager-preview unit tests were removed — those operations now live in and are tested through `core/engine`/`core/commands` (`test_split_merge`, `test_engine_commands`, …). Run `pytest` for the current pass count.

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

Current stable tag: **v3.7.0**

---

## Open / deferred items
- **Manual tests 01–04 still describe legacy Tk flows** — after the v3.6.0 Tk
  removal, their step wording (menus, toolbar) is stale; re-verify/rewrite each
  against the React UI. The features themselves are unchanged.
- **`PDFNode` is now a pure `.belegtool` I/O carrier — DONE.** The dead preview/
  operation machinery was removed: `pdf_node.py` no longer carries `preview_lazy`/
  `preview_folder`/`update_preview`/`_create_previews`/`compress*`/`select_compression_method`/
  `rotate`/`split`/`merge`/`from_pdf`/`commit_changes`/`reset_compression`/`move` or the
  `_*_preview_pages` + background-compress threads; `preview_page.py` is deleted and the
  `generate_previews` flag is gone from `PDFStorage` (load is always bytes-only). What
  remains is the carrier surface (constructor, `set_original_and_current_data`, `to_dict`,
  `from_recursive_array`, `copy`, the data properties, `_concat_children_data`, `is_valid`).
  The redundant PDFNode-op unit tests were dropped (the operations live in and are tested
  through `core/engine`/`core/commands` — `test_split_merge`, `test_engine_commands`, …);
  [`test_belegtool_roundtrip`](tests/test_belegtool_roundtrip.py) guards the carrier.
- **Headless import is bytes-only end to end** — plain-PDF *and* archive/email
  paths store bytes only (the carrier never renders); page count uses `fitz.page_count`;
  the `/JSONStructure` metadata
  parse is gated on a cheap `b"/JSONStructure" in data` byte check (the marker
  survives pikepdf's compress+linearize, so `.belegtool`/structured-PDF imports are
  still honored — locked by `test_structured_pdf_import_honors_json`). Warm import is
  ~1 ms; the remaining cold-open cost is Windows Defender scanning the file, outside
  our control.
- **Windowed render cache — wired into the UI; background filler active (thread-pooled).**
  Done: pure `predict_window`/`next_fill_target` ([`core/render_policy.py`](core/render_policy.py)),
  `RenderService`/`RenderCache` ([`services/render_service.py`](services/render_service.py)),
  `CoreApi.render_window`/`page_count`/`page_dims` (+ HostApi + `core.js`), and the
  virtualized [`Preview.jsx`](webui/src/Preview.jsx) (IntersectionObserver +
  aspect-ratio placeholders + ±5 prefetch + per-node scroll memory). **Every leaf
  preview uses it — both the plain stored bytes and the compression working-preview**
  (`render_compressed_window` renders the variant through the same cache, keyed by the
  variant's `crc32`, so the service stays compression-agnostic). Only folders use the
  all-pages path. On each request the service **seeds** the surrounding window in the
  background (`RenderService.seed` → parallel `fill_until_idle`) on a capped,
  below-normal-priority pool that yields to foreground (generation token) and to a busy
  box (real `SystemCpuSampler`, terminal-server fair). ⚠ **Needs on-screen QA** (MT-39).
  ⚠ **Multicore caveat:** thread parallelism is GIL-limited for PyMuPDF (~1.2×), so this
  overlaps prefetch with idle rather than saturating cores; **true multicore would need a
  process pool** (~2.4× measured, warm+chunked) plus `multiprocessing.freeze_support()` in
  `host.py` and testing inside the packaged exe — deliberately deferred (2026-06-03).
- **Compression speed for large nodes — partially addressed.** The rasterize loop in
  `compress_pdf_bytes._render_pdf_as_images` runs across the below-normal pool only for
  large docs (`_PARALLEL_MIN_PAGES`, default **50**; smaller render inline). Same GIL
  caveat (~1.2× via threads), so the floor is high on purpose — the pool overhead isn't
  worth it below that. The **bigger**
  remaining win is *work-avoidance*: the compression dropdown (`compress_options` →
  `compress_all_methods`) still renders **all pages × every image method** just to size
  them — a sample-based estimate + persisting committed variants (Phase 4) would cut the
  felt wait far more than threads do. Deferred per user decision (2026-06-03).
- **Zammad integration** — deferred, not started yet

---

## UI conventions
- React + Vite SPA in `webui/`; rendered inside the pywebview host
- Toolbar: open/import/save/export/new-window/undo/redo ([`App.jsx`](webui/src/App.jsx))
- Tree + drag-and-drop in [`Tree.jsx`](webui/src/Tree.jsx); right-click ops in [`ContextMenu.jsx`](webui/src/ContextMenu.jsx)
- Compression controls (method dropdown incl. `jpg_color`, DPI, apply/reset) in [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)

---

## Beta-tester feedback infrastructure

GitHub issue forms + docs onboard beta testers and route feedback. **Treat this as
part of *definition of done*:** when any of the baked-in facts below change, update
the matching files in the **same session** — stale tester docs cause noise (people
report known gaps, give the wrong version, etc.).

| File | What it is |
|---|---|
| [`.github/ISSUE_TEMPLATE/bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml) | Bug form: version, install method, Windows ver, Office y/n + apps, workflow/manual-test, repro, expected/actual, evidence, **required "not a known gap" checkbox** |
| [`.github/ISSUE_TEMPLATE/feature_request.yml`](.github/ISSUE_TEMPLATE/feature_request.yml) | Problem → solution → workflow → alternatives |
| [`.github/ISSUE_TEMPLATE/beta_feedback.yml`](.github/ISSUE_TEMPLATE/beta_feedback.yml) | Soft UX form: impressions, confusion, would-you-use (yes/maybe/no), one change |
| [`.github/ISSUE_TEMPLATE/config.yml`](.github/ISSUE_TEMPLATE/config.yml) | Disables blank issues; routes questions to Discussions + links `BETA_TESTING.md` |
| [`BETA_TESTING.md`](BETA_TESTING.md) | One-page tester onboarding (get/run both paths, test path, known gaps, feedback routing) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Build/run from source, fixtures, manual-test pointer, how to file each feedback type |

**Facts baked into these files — keep them in sync with the source of truth:**
- **Version `3.7.0`** (bug form default + BETA_TESTING heading) → bump when `version_info.py` changes.
- **Windows 10/11 only**; **Office-via-COM** caveat for Word/Excel/PPT import.
- **Two known gaps that must NOT be reported as bugs** (the bug form's required
  checkbox enforces this): (1) export >100 pages → single PDF, auto-split not wired
  into the UI; (2) compression irreversible after save ("bereits komprimiert (keine
  Quelle)"). **If either gap is fixed, remove it from the checkbox, BETA_TESTING.md
  §4, and CONTRIBUTING.md** — otherwise testers are told a working feature is broken.
- **Manual tests `05`–`07` are current; `01`–`04` are stale (removed Tk GUI).** When
  01–04 are rewritten against the React UI, drop the "stale" wording everywhere it
  appears (BETA_TESTING.md §3, CONTRIBUTING.md, `manual_tests/README.md`).
- **Two run paths** (prebuilt onedir folder; from source: Python 3.12 + Node, `pip
  install -r requirements.txt`, `cd webui && npm install && npm run build`, `python
  host.py`) and **no published Release yet** — update BETA_TESTING.md §1 once a
  Release/installer exists.
- **Fixtures in `tests/data/input/`** (regen `python tests/make_fixtures.py`).
- The `config.yml` and template links hardcode the repo URL
  `tobiasheinrichfaska/DigitalerUnterlagenOrdner` and the `master` branch.

⚠️ **Manual GitHub steps (not in the repo):** Discussions must be enabled in repo
**Settings → Features**, and a Release published (or the build folder zipped) for
the prebuilt download path to work.
