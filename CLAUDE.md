# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: **React + Vite SPA inside a pywebview host** (Edge WebView2). Version: **3.10.0**.

Entry point: **`host.py`** — the single pywebview host. `python host.py` launches
the GUI; `python host.py <file.belegtool>` opens that file on startup.

> **v3.6.0 removed the legacy Tk GUI** and the dual `app.py` entry point. The only
> front end is now the React/pywebview GUI; `host.py` is the sole entry. Removed
> files: `app.py`, `launch_util.py`, `belegtool_main.py`, `panel_controls.py`,
> `view_tree.py`, `view_preview.py`, `status_display.py`, `test_mode.py` (and their
> tests). `tkinterdnd2` is gone from `requirements.txt`.

---

## Architecture

**Top-level layout (Python):** `core/` = pure data-driven domain (model, commands,
engine, bridge, session, api, render_policy) with `core/ipc/` for the named-pipe
transport; `services/` = stateful infra (render cache, CPU fairness, variants);
`formats/` = `.belegtool` I/O + conversion (pdf_node, pdf_storage, toc_export,
compress_pdf_bytes); `universal_importer/` = multi-format import package;
`datev/` = the lazy DATEVconnect integration (DATEV-mode only; never imported when
off — `inapp`, `client`, `writeback`, `provenance`, `config`, `transport`, `types`);
`infra/` = ports + per-user state (tasks, log_config, tools, `settings.py`,
`file_lock.py`, `window_geometry.py`); `host.py`/`version_info.py` =
entry/config; `webui/` = React frontend (`src/lib/` holds its UI-free logic).

### Entry point & host

| File | Role |
|---|---|
| `host.py` | **The single entry point.** pywebview host: one shared `CoreApi`, one `HostApi` **per window** (bound to the window uid). Native dialogs, `new_window`, per-window close guard (`window.__belegDirty`), startup `_prewarm` of the heavy PDF libs. The **first** window **persists its geometry** (size/position/monitor) to `%APPDATA%\…\window.json` on close and restores it on next launch; a saved geometry whose monitor is gone falls back to the default (validated by the pure [`infra/window_geometry.py`](infra/window_geometry.py), tested). |

### Data model

| File | Role |
|---|---|
| `formats/pdf_node.py` | `PDFNode`: serialization carrier for the `.belegtool` I/O path only (bytes + metadata, `to_dict`/`from_recursive_array`/`copy`). **No rendering, no operations** — split/merge/rotate/compress live in `core/engine` |
| `formats/pdf_storage.py` | `PDFStorage`: JSON serialization, export with TOC, .belegtool format |

### Import & Export

| File | Role |
|---|---|
| `universal_importer/` | Multi-format import **package**: `importer.py` (the `UniversalImporter` detect+dispatch class), `converters.py` (per-format functions: images jpg/png/webp/heic, Office via COM, txt/html + the `data:`/`cid:` link guard), `archives.py` (ZIP/TAR/email extraction + bomb guards). `__init__` re-exports the public surface. |
| `formats/toc_export.py` | PDF export with printed TOC, clickable annotations (pikepdf), sidebar bookmarks, auto-split >100 pages |
| `formats/compress_pdf_bytes.py` | Render-based compression (JPG/PNG), pikepdf structural compression, method comparison |

### Utilities

| File | Role |
|---|---|
| `infra/tools.py` | `sanitize_pdf`: repair broken PDFs (xref/object streams) via pikepdf — a no-op on readable files. Wired into `PDFStorage._load_pdf`'s plain-PDF branch (never the `.belegtool` path). |
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.10.0) |
| `infra/log_config.py` | Logging setup |

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
| `infra/tasks.py` | Execution **port**: `submit(fn)` (swappable executor — daemon thread by default, pool/sync later) and `run_on_ui_thread(fn)` (UI-thread dispatch; inline when headless). Used by `universal_importer`. |

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
| `core/ipc/{server,pipe,protocol,client}.py` + `core/cli.py`, `core/__main__.py` | Per-user named-pipe **core service** (Step 0a): IPC transport (`core/ipc/`) + CLI entry points (`core/cli`, `python -m core`) |

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
| `core/api.py` | `CoreApi` façade (JSON in/out, one `DocumentSession` per window): `open/save/dispatch/undo/redo/render_window/render_compressed_window/page_count/page_dims/compress_options/import_paths/import_bytes/export/config`. (The whole-doc `render` is IPC/test-only — the pipe server still dispatches it; `render_compressed` is test-only; neither is on the JS bridge since 2026-06-12.) Per-session `dirty` tracking. `dispatch`/`undo`/`redo` share one post-mutate hook (`_after_mutate`): revive stale cancel tokens of ids back in the doc (delete→undo regression), prune the render cache, re-kick the prefetch. **`close_session`** frees a closed window's session (bytes, undo log, page-count cache, lock, materialized-view temp dir) and prunes the render cache — called from `host._bind_close`; `sweep_stale_view_dirs` clears crashed-session `beleg_view_*` temp dirs at startup (>1 day old); a live view dir's mtime is also refreshed via render traffic (rate-limited), so an unsaved view window open >24 h stays sweep-safe. |
| `webui/src/App.jsx` | Main component: toolbar (open/import/save/export/new-window/undo/redo), tree + preview panes, OS file-drop, keyboard shortcuts, dirty/notice state |
| `webui/src/Tree.jsx` | Tree view + all drag-drop: internal move (into/before/after, slide-to-level ghost) **and** OS file import sharing the same zones |
| `webui/src/PreviewControls.jsx` | Lazy working-preview compression (method dropdown loads on open → "Kompression läuft", apply via "Lesbarkeit geprüft"), rotate |
| `webui/src/ContextMenu.jsx`, `lib/core.js` | Right-click ops (incl. Merge→1 PDF / In neuen Ordner / Status incl. "Kein Status" + folder cascade); thin `window.pywebview.api` wrapper. Pure frontend logic lives in `webui/src/lib/` (`core.js`, `selection.js` incl. `mergeableIds`, `treeNav.js`, `status.js`, `messages.js`). |
| `webui/src/lib/status.js` | **Pure** status-dot aggregation (leaf/folder, red→yellow→green + black) + `hasUndecided` for the front compression dot. Tested in `status.test.js`. |
| `webui/src/HelpModal.jsx`, `help/content.js` | How-to Help modal (separate from the main UI language switcher): 🇩🇪/🇬🇧 flags toggle the two authoritative versions; help text authored best-effort for all UI languages, unknown → EN fallback; GitHub/mailto correction links. |
| `webui/pdf-tool.html`, `webui/src/pdftool/` (`main.js`, `source.js`) | **PDF-Tool surface** (2nd Vite entry, PDF.js): the host routes a `.pdf`/node binding here (`host._entry_for_kind` / `startup_kind`), it fetches the bound bytes over the bridge (`CoreApi.get_pdf_bytes` / `open_node_in_pdftool` / `close_pdftool`) and renders a **selectable text layer + interactive AcroForm**, plus an **„✎ Text" tool** (PDF.js FreeText editor) and **„💾 Speichern"** → `saveDocument()` → `save_node_back(session, b64)` → `SetNodeBytes` (new source on the node, undoable in the organizer). Added text round-trips as editable FreeText on reopen. `source.js` (`chooseSource` / `base64ToUint8` / `uint8ToBase64`) is the pure, unit-tested logic. Design + roadmap: [`docs/pdf-tool.md`](docs/pdf-tool.md). |

**Run:** dev — `cd webui && npm run dev` then `set BELEG_DEV=1 && python host.py`;
prod — `cd webui && npm run build` then `python host.py`. **Unit tests:** `cd webui
&& npm test` (Vitest + jsdom; `src/lib/core.test.js` smoke-tests the `core.js` bridge —
method-name mapping and the `pywebviewready` wait/fail-fast). **Manual tests:**
[`manual_tests/05_react_ui.md`](manual_tests/05_react_ui.md).

**Two test layers (frontend):**
- **jsdom unit/component** (`npm test`, Vitest, fast) — covers logic (`src/lib/`), and
  components/integration by rendering against a **mocked `window.pywebview.api`** (a Proxy
  recording calls). Includes selection/multi-select + the keyboard multi-node `MoveMany`
  carry and its partial-folder resolver parity with drag (`App.select.test.jsx`,
  `App.moveresolver.test.jsx`), the dialogs (`ExportDialog`/`SaveDialog`/`HelpModal`), and
  `StatusBar`/`PreviewPane`/`TagEditor`/`TagViewBar`. Vitest's `include` is pinned to
  `src/**` so it never picks up the e2e specs.
  - ⚠️ **No `vi.mock()` in this project's tests.** The `forks`/`threads` pools crash on this
    toolchain (vitest 4.1.8 + Node 24 + Vite 8 → *"failed to find the current suite"*), so
    `vite.config.js` forces `pool: 'vmThreads'` — and **`vi.mock()` does not take effect under
    `vmThreads`** (the real module loads instead, silently). Mock the **`window.pywebview.api`
    bridge** (the Proxy pattern in `test-setup.js`) and pass real child components / props
    instead. History: `StatusBar.test.jsx` + `PreviewPane.test.jsx` were added on 2026-06-15
    using `vi.mock` and **never passed** under `vmThreads` (7 red), yet were reported green by
    inheriting the count — rewritten `vi.mock`-free on 2026-06-16. See the workspace
    **Test-result integrity** rule.
- **Playwright e2e** ([`e2e/`](webui/e2e), `npm run test:e2e`, real Chromium) — covers the
  two layout-dependent things jsdom can't: **scroll virtualization** in [`Preview.jsx`](webui/src/Preview.jsx)
  (binary-search on real `offsetTop`/`scrollTop`) and the **HTML5 drag-and-drop** handshake
  in [`Tree.jsx`](webui/src/Tree.jsx). A browser has no Python host, so each spec injects a
  stub bridge before load ([`e2e/bridge.js`](webui/e2e/bridge.js)). First run needs
  `npx playwright install chromium`. `webServer` runs `npm run dev` on port 5178.

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
- **Office** (Word/Excel/PPT **+ OpenDocument .odt/.ods/.odp**) → Win32-COM → PDF
  (ODF opens through the matching app — Word/Excel/PowerPoint; **verified end-to-end on a
  real Office machine** by the golden round-trip test, [`tests/test_office_golden.py`](tests/test_office_golden.py))
- **Archives** (ZIP, TAR) → structure preserved, loaded recursively
- **Email** (eml, msg) → body + attachments extracted as tree structure

**Import-routing fix (2026-06-13, audit M-1/L-1/L-2):** `UniversalImporter.get_supported_extensions()`
now **always** lists Office/ODF — the old runtime COM probe (`_has_word/_excel/_powerpoint`,
`_detect_office_support`, `initialize`/`initialize_async`) was never wired in (it would have
launched Word/Excel/PowerPoint just to detect them) so it stayed False forever, which made the
**bytes path reject every Office/ODF member inside a zip/email**. That dead probe is removed;
conversion still degrades to "nicht importierbar" if Office isn't installed (same as the path
branch). The import dialog filter (`host._import_file_types()`) is now derived from
`get_supported_extensions()` (lazily, to keep the heavy COM import off startup), so newly
supported formats — incl. ODF — appear instead of the old hand-maintained subset.

**Import hardening (2026-06-12):** the EXE/script signature + magic-byte gate
(`verify_content_matches_extension`) runs on **both** branches — archive/email
members (bytes) *and* single-file imports (path: import dialog / OS drag). OOXML
Office files are pre-scanned (`converters.scan_ooxml_external_targets`) for
`TargetMode="External"` non-hyperlink `.rels` targets (http/https/ftp/ftps/file:/UNC —
attached template, linked content) and **refused** before any COM open (NTLM-hash
leak / SSRF mitigation). The scan **fails closed** for ZIPs: a file that
`is_zipfile` accepts but whose `.rels` can't be scanned (corrupt header, exotic
method, > entry cap, or an oversized `.rels` that **truncates** at the 4 MB read cap
— a legit `.rels` is tiny, so an oversized one hiding a target past the cap is itself
suspicious) returns `SCAN_UNREADABLE` → same refusal (Word's lenient OPC
parser could otherwise resolve a target our `zipfile` couldn't read). Genuine
non-zip legacy OLE `.doc/.xls/.ppt` stays fail-open — no `.rels` exists, there only
the COM guards apply; **ODF (`.odt/.ods/.odp`) is a ZIP but has no `.rels` either, so
the scan returns `None` (fail-open) and the COM guards are likewise the active
protection for it.** Office apps are `Quit()` in `finally`, so a
failed conversion leaks no hidden WINWORD/EXCEL/POWERPNT. Rendering clamps DPI to
a per-page pixel budget (`services/render.MAX_RENDER_PIXELS`) against oversized-
MediaBox allocation bombs — on the preview paths **and** the compression raster
path (`compress_pdf_bytes._render_one_page`, which alone only clamped width).

### Tree operations
Split, merge (with DPI conflict check), create folder, delete, rename, deep copy, drag-and-drop.

**Keyboard structuring** (`webui/src/lib/treeNav.js` pure helpers + `App.jsx` `onKey`):
↑/↓ navigate the visible rows; ←/→ collapse/expand a folder (or step out/in).
**Insert** grabs the selected node (dashed outline); while grabbed, arrows move it
**optically** (↑/↓ reorder, → nest into the folder above, ← out a level) — nothing is
committed until **Insert** drops it (a single undoable `Move`); **Esc** cancels and
reverts. (Ctrl is multi-select, so it can't be the move modifier.)
**Multi-node carry:** when more than one node is selected, Insert locks in the whole
selection — the **primary** moves optically while the rest stay visibly selected, and
the block follows on drop as **one undoable `MoveMany`**. The drop slot is computed by
[`moveManyDrop`](webui/src/lib/treeNav.js) (pure, tested) in the core's pre-removal frame
— the original index of the first non-carried node after the primary, or append — so the
block lands exactly where the primary was dropped (the core discounts the moved-out
siblings). Wired in [`useKeyboard.js`](webui/src/hooks/useKeyboard.js) → `App.onMoveMany`.

**Folder collapse** is a **persisted** `Node.collapsed` field (set via `SetCollapsed`
/ `SetAllCollapsed` commands — undoable, marks dirty, round-trips in `.belegtool`).
Chevron in the tree, ←/→ keys, and context-menu **Aufklappen/Zuklappen** + **Alle
auf-/zuklappen**. Cuts scrolling on large trees.

### Tags & tag views (v3.8.0)
Per-node free-form labels (**persisted** `Node.tags`, set via the `SetTags` command;
round-trips in `.belegtool`). Tagging is **off by default** (toolbar 🏷️ toggle) and
**auto-enables** when a loaded file already has tags. Editor + favourites (localStorage)
in [`TagEditor.jsx`](webui/src/TagEditor.jsx); row chips in the tree. All view logic is
UI-free and tested in [`webui/src/lib/tags.js`](webui/src/lib/tags.js):
- **Search filter** ([`filterTree`](webui/src/lib/tags.js)) — by **tag only** (never node
  name). A tag match keeps the node's **whole subtree** (downward inheritance); ancestors
  of a match are kept as containers, non-matching siblings hidden.
- **Group by tag** ([`groupByTag`](webui/src/lib/tags.js)) — one synthetic folder per OWN
  tag; a tagged **folder** is kept whole, a tagged leaf keeps its **ancestor path**; nodes
  may appear under several tags (duplication intended); fully-untagged paths → „Ohne Tags".
- **View = read-only structure.** While a search/group view is active the displayed
  positions are virtual, so reorder / import / add-folder / **delete** / group / merge /
  split are disabled (Tree `reorderDisabled`, `useKeyboard` `reorderEnabled`, Toolbar
  `editLocked`, ContextMenu `editLocked`). Content edits (rename, status, compression)
  stay available. Bar UI in [`TagViewBar.jsx`](webui/src/TagViewBar.jsx).
- **Open view in new window** ([`CoreApi.materialize_subset`](core/api.py) →
  `HostApi.open_view_in_new_window`) — writes a temp `.belegtool` of just the **displayed**
  nodes ([`displayedNodeIds`](webui/src/lib/tags.js)) in **normal tree order** (grouping not
  applied), named `<tag> - <old name>`, and opens it as a fresh editable window. Offered
  only when a **tag search** is active (not gated by group-by).

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

### Status system (per node) — dots (v3.9.0)
Status values: `""` (**no status — the new default**, no dot), `zu erfassen` (yellow),
`erfasst` (green), `vorjahreswert` (red). Shown as **trailing dots** on the row
(pure logic in [`webui/src/lib/status.js`](webui/src/lib/status.js), tested):
- **Leaf:** its own status dot (or none).
- **Folder:** one dot per distinct descendant status (red→yellow→green) **+ a black dot**
  when descendants are mixed with/without status; all-no-status or empty folder → no dots.
  Deep aggregation (children + grandchildren).
- **Set status** via right-click. On a **folder** it **cascades to every descendant
  document** (`SetStatus` handler). "Kein Status" clears.
- **Merge:** all inputs same status → kept; any difference → no status. **Split:** parts
  inherit the original's status.

### Compression "undecided" marker + persisted no-gain (v3.9.0)
- A **red dot at the front** of a leaf row = compression **not yet decided**
  (`compression_undecided` overlay in [`core/api.py`](core/api.py)): true unless the node is
  applied (`is_compressed` = "Lesbarkeit geprüft"), `no_compression`, or auto-confirmed
  no-gain. Folder rows show it if any descendant leaf is undecided.
- **Persisted no-gain:** `Node.compression_no_gain` — when evaluation finds nothing smaller,
  the decision is written **live into the document** the moment `compress_options` returns no
  options, via the silent `SetNoGain` command (`CoreApi._mark_no_gain` →
  `DocumentSession.apply_silent`: **no undo/redo, no dirty, not in the event log** — it is a
  derived verdict, not a human edit). It round-trips in the `.belegtool` and is **cleared on
  rotate**. So a "nothing smaller" node is not re-evaluated on load and shows no red dot.
  Auto-compute on view skips these. `CoreApi._bake_no_gain` still runs at save as a fallback.
  ⚠ **Fixed 2026-06-25:** before this, the verdict lived only in the engine's **bounded
  16-entry variant cache** (`evaluated()`), so on a document with >16 incompressible leaves the
  earliest verdicts were evicted → the red dot **reappeared on move / reopen**. The live
  `SetNoGain` write makes it durable. Cancelled evaluations (token set) are **not** flagged.
- **Proactive sweep:** after a document loads, [`App.jsx`](webui/src/App.jsx) evaluates the
  **cheap (≤5-page) undecided leaves** in the background — sequential + cancellable, reusing the
  same `compressOptions` call as auto-compute — so their front dot resolves **without needing a
  view**. As each resolves, `setUndecided` updates the dot (no-gain → cleared); the viewed node
  and manual/large-node checks update instantly via `PreviewControls onResolved`. Large nodes
  stay lazy. The verdict persists at save (the sweep warms the memo `_bake_no_gain` reads).

### Rename & Help (v3.9.0)
- **F2** renames the selected node inline ([`Tree.jsx`](webui/src/Tree.jsx)).
- **❓ Hilfe** opens a how-to modal ([`HelpModal.jsx`](webui/src/HelpModal.jsx),
  content [`help/content.js`](webui/src/help/content.js)): DE + EN are the two authoritative
  versions (🇩🇪/🇬🇧 flags), help text authored best-effort for the other UI languages, unknown
  → EN fallback; footer reports translation corrections via a pre-filled GitHub issue or `mailto`.

### Export
- Single PDF with table of contents (TOC), clickable links, sidebar bookmarks
- **Export-options dialog (v3.9.0)** ([`ExportDialog.jsx`](webui/src/ExportDialog.jsx), asked
  before the native save dialog): toggle **TOC** (+clickable links), **tag index** (+links —
  offered only when the document has tags), and **PDF bookmarks**. Options flow
  `exportPdf → export_dialog → CoreApi.export(options) → toc_export.export_pdf`.
- **Tag index (v3.9.0)** ([`toc_export._build_index_items`](formats/toc_export.py)): a
  „Stichwortverzeichnis" of tags → documents (effective tags = own ∪ ancestor-folder tags),
  alphabetical, with content page numbers and clickable links — rendered like the TOC, in the
  front matter after it. `export_pdf(nodes, path, options)` builds `[TOC][index]` before the
  content; page numbers/links/bookmarks account for the front-matter offset.
- Export default filename = the **document name + `.pdf`** (was "Export.pdf").
- Auto-split at >100 pages with cross-references
- `.belegtool` format: a single PDF whose pages are the nodes' **effective bytes**
  (`current_pdf_data`), with the tree serialized into the `/JSONStructure` metadata
  key. Import gates the (expensive) structure parse on a cheap `b"/JSONStructure"`
  byte check.

### File lock — single-writer (v3.9.0, off by default)

For a shared (SMB / client-server) store: when enabled, opening a `.belegtool` holds an
**exclusive Win32 handle** ([`infra/file_lock.py`](infra/file_lock.py)) for the window's
lifetime, so only one person edits at a time. Share mode `FILE_SHARE_READ` (deny write +
delete, allow read) — bit-for-bit Acrobat's; the OS frees it on process death (no stale lock).

- **Enable:** environment variable `BELEG_FILE_LOCK=1` (any of `1/true/yes`). **Off by default**
  (a graphical setting is deferred). Windows-only; non-Windows / errors fall back to no lock.
- **Lifecycle** ([`CoreApi`](core/api.py)): `open` acquires (→ `{ok:false, code:"in_use"}` with a
  German message if already locked); each window's session keeps its lock in `_locks[sid]`;
  the window-close guard ([`host.py`](host.py) `_bind_close`) calls `CoreApi.release`; save-as
  re-locks the new file.
- **Saving under the lock:** the handle denies our own `open('wb')`, so the locked save goes
  **through the handle** in a single write — `PDFStorage.to_bytes()` + `embed_variants_bytes()`
  built in memory, then `FileLock.overwrite`. In-place overwrite isn't atomic, so a sibling
  **`.bak`** of the previous bytes is written first and removed only after a successful flush;
  `open` **restores from `.bak`** if it finds the file truncated (interrupted save). Lock-off
  saving is unchanged (the original two-write path).
- **Tests:** [`tests/test_file_lock.py`](tests/test_file_lock.py) (14, primitive incl. OS
  auto-release + thread race), [`test_save_bytes_pipeline.py`](tests/test_save_bytes_pipeline.py)
  (bytes-pipeline parity with the path-based save/embed),
  [`test_file_lock_integration.py`](tests/test_file_lock_integration.py) (in-use, locked
  in-place save, save-as re-lock, `.bak` restore). Windows-only suites skip elsewhere.
- **Deferred:** graphical on/off setting; Office-style autosave/recover of *unsaved* changes;
  read-only fallback when a file is in use.

### In-app DATEV integration (v3.10.0, DATEV-mode only, lazy-loaded)

Files / writes documents back into the local **DATEV Dokumentenablage** (DokAb) via
DATEVconnect. **Off by default** behind a per-user setting; when off, the heavy `datev`
package is **never imported** (normal launch stays lean). Authoritative design:
[`docs/datev-integration-design.md`](docs/datev-integration-design.md); the live-verified
mechanics: [`docs/datev-dokumentenablage-recipe.md`](docs/datev-dokumentenablage-recipe.md)
and [`docs/datev-provenance.md`](docs/datev-provenance.md).

- **Setting + toggle** ([`infra/settings.py`](infra/settings.py)) — `datev_mode` (+ optional
  `dms_base_url`) persisted to `%APPDATA%\DigitalerUnterlagenOrdner\settings.json`, the sibling
  of `window.json`. ⚠️ **Terminal-server safe: strictly per-user** (`%APPDATA%` Roaming is the
  user's own profile, never machine-wide) — required because DATEV authenticates via **Windows
  SSO as the logged-in user**. The header **„DATEV"** button ([`DatevBar.jsx`](webui/src/DatevBar.jsx))
  flips it via `HostApi.set_datev_mode` → `CoreApi.set_datev_mode`.
- **Lazy service** ([`datev/inapp.py`](datev/inapp.py) `DatevService`) — built on first use over
  the reusable, injected-transport [`datev/client.py`](datev/client.py) (SSO curl). Imports the
  `datev` package only when mode is on. `CoreApi._datev_get_service()` is the gate.
- **Provenance** — the DATEV origin `{doc_guid, file_id, structure_item_id,
  correspondence_partner_guid, source_name}` lives on the **root** `Node.datev` field and
  **round-trips in `.belegtool`** (threaded through `model`/`pdf_node`/`bridge`/`pdf_storage`;
  set/cleared by the in-process **`SetDatev`** command, applied silently — origin metadata, no
  undo/dirty). The write-back **baseline** (opened sha256 + `change_date_time` + checked_out)
  is per-session runtime state in `CoreApi._datev_baseline`, **not** persisted.
- **On open** (`CoreApi._datev_capture_on_open`) — a DATEV **checkout path**
  (`…\<doc-guid>\<file-id>`, via `parse_checkout_path`) captures provenance + baseline, shows a
  „from DATEV" badge, and warns up front if the document was already checked out.
- **On save** — the guarded write-back: `HostApi.save_to_datev` asks „nach DATEV zurückschreiben?",
  then `CoreApi.datev_save_back` re-reads the server NOW and runs the **pure**
  [`datev/writeback.py`](datev/writeback.py) `decide_save_back` (not checked out · `change_date_time`
  unchanged vs baseline · server bytes == opened original). `ok` → backup the fetched server
  bytes to `%APPDATA%\…\datev_backups\`, then `upload_document_file` → `update_structure_item`
  (the **stable** structure-item id; DokAb overwrites, no revision). **Any non-ok verdict
  (`declined`/`locked`/`conflict_changed`/`conflict_content`/`no_structure_item`) writes
  NOTHING** and the UI falls back to a filesystem save.
- **Save As clears provenance** (Save As breaks the DATEV link). A not-connected file offers
  **„nach DATEV ablegen"** = the create flow (`CoreApi.datev_file` → upload + `create_document`,
  Mandant via `resolve_client_guid`, user via SID match, no state for class 1), then adopts the
  new provenance.
- **Export → DATEV (same client)** — the export dialog gains „Nach DATEV ablegen (gleicher
  Mandant)" when connected; `CoreApi.datev_export` exports (single **or split**, honouring the
  options) and files **every produced PDF** as its own new DATEV document under the source's
  Mandant.
- **Tests:** the pure logic + orchestration are covered headless (`tests/test_settings.py`,
  `test_datev_provenance_roundtrip.py`, `test_datev_inapp.py` with a fake client,
  `test_datev_coreapi.py` with a fake service; the existing `test_datev_client.py` /
  `test_datev_writeback.py`). Frontend: `webui/src/DatevBar.test.jsx`, `lib/datev.test.js`, the
  export-option cases in `ExportDialog.test.jsx`. Live end-to-end is the
  [`manual_tests/10_datev.md`](manual_tests/10_datev.md) checklist (needs a DATEVconnect box).
- The standalone probe (`datev/probe_gui.py` → `DATEV-Probe.exe`) is **research tooling**, not
  shipped in the BelegTool release.

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
unbounded **persisted** layer next to the LRU memo, guarded by the memo lock).
**Bomb-guarded at BOTH layers (2026-06-12):** `variant_blobs.unpack` enforces an
actual-read per-blob total cap (500 MB) + entry-count cap (500); `seed_variants_from_file`
caps the `variant_*` attachments processed (500) **and** — one layer up, where the
bomb actually detonates — never uses pikepdf's uncapped `read_bytes()`: it reads the
attachment's RAW stream and inflates the `/FlateDecode` incrementally
(`_read_attachment_capped`) with a per-attachment decoded cap + a running-total cap
across all attachments (both 500 MB, mirroring `unpack`). A hostile `.belegtool`
can't OOM the app on open; an over-cap blob/attachment is skipped whole (variants
just recompute). Legit blobs are stored ZIPs of already-compressed PDFs (raw ≈
decoded), so the caps never bite them. For id-keyed blocks to match on
reload, the node **`uid` is now persisted** in `/JSONStructure` (`to_dict`/`_parse_node`).
This does **not** reverse drop-source-on-save: only nodes that *still have a source*
(uncommitted) store variants; a committed node has none. Per-file variant budget caps
the bloat. ⚠ Variants live in the file → it grows; not a separate sidecar.

---

## Build

### Prerequisites
- Python 3.13 in PATH — the build pins it via the `py -3.13` launcher (`$PyVer` in `build.ps1`); running from source works on 3.12+
- Node.js (the build runs `npm run build` in `webui/` first)
- **Edge WebView2 Runtime** on the *target* machine (Win11 has it in-box; Win10 / minimal
  images / Windows Sandbox may not). Missing → the React UI renders **blank**. `host.py`
  checks at startup (`_webview2_installed`) and shows a message + download link instead of a
  blank window (`BELEG_SKIP_WEBVIEW2_CHECK=1` bypasses). Distribution should ensure it: MSIX
  declares it as a dependency; the zip should bundle the Evergreen bootstrapper. See
  [`docs/microsoft-store-plan.md`](docs/microsoft-store-plan.md).
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

### Full preflight / audit gate — run ALL FIVE layers

⚠️ A complete check (an `/audit` preflight, a pre-release gate, "run all tests") is **all
five** layers below — not just `pytest` + `npm test`. The Playwright **Chromium** e2e suite
is a **separate** npm script (`test:e2e`, NOT part of `npm test`), so it is easy to skip and
the drag-drop + preview-virtualization layer can regress unseen. Run every one:

```powershell
.build_venv\Scripts\python.exe -m pytest          # Python suite (incl. office golden; ~498)
cd webui ; npm run lint                            # eslint — 0 errors
cd webui ; npm run test:all                        # vitest jsdom (~281) + Playwright REAL Chromium e2e (3)
cd webui ; npm run build                           # vite build must succeed
```

(`npm run test:all` = `vitest run && playwright test` — runs both frontend layers so the
e2e layer can't be skipped. First run on a fresh machine: `npx playwright install chromium`.
You can still run them apart with `npm test` / `npm run test:e2e`.)

Do **not** report a clean test run unless `test:e2e` was among them. Chromium is already
installed in this workspace's playwright cache; if a fresh machine lacks it, run
`npx playwright install chromium` first.

### What each layer covers

Framework: `pytest`. Tests in `tests/` cover the `.belegtool` carrier (`pdf_storage`, the `pdf_node` round-trip), compression/import (incl. `test_compress_parallel` — content+order match of the multi-worker path), the data-driven `core/` (model, commands, engine, session, bridge, api, ipc, **render_policy**), the render helpers, the CPU-fairness primitives (`test_cpu`), and the pywebview host glue (`test_host.py`). A real-Office COM round-trip is in `test_office_golden.py` (marked `office`; runs by default, auto-skips without Office; fixtures from `make_office_fixtures.py`). The legacy PDFNode-operation/eager-preview unit tests were removed — those operations now live in and are tested through `core/engine`/`core/commands` (`test_split_merge`, `test_engine_commands`, …). Run `pytest` for the current pass count.

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

Current tag: **v3.10.0** (beta) — icon-only toolbar, Save split-button, multi-select tagging,
„Neuer Ordner" at selection, zoom-keeps-position, nested archive/mail + subfolders, configurable
export split, PDF-Tool text editor, and the **in-app DATEV integration** (DATEV-mode only).

---

## Known Limitations

Current accepted shortcomings and non-obvious behaviours (lift into release notes as needed).
Deferred *features* and the full rationale live under **Open / deferred items** below.

- **Windows-only.** PyInstaller `win64`, Edge WebView2 GUI, hard `pywin32`/`pythonnet` deps,
  COM-based Office import. The PDF core is cross-platform but no port is maintained
  (community RFC: [`docs/cross-platform-port.md`](docs/cross-platform-port.md)).
- **Split export uses its own TOC, not the front-matter toggles.** Splitting into several files
  (Open items #13, shipped) always renders a per-file TOC with cross-references to the other parts,
  and **ignores the tag-index / PDF-bookmarks / TOC-links checkboxes** (those apply to single-file
  export only). Unifying the split path with the full front-matter options is a follow-up. The
  page-level („mitten im Dokument") cut copies pages via `PdfWriter`, so it inherits the same
  text-PDF limitation as the normal export (named destinations / link annotations dropped).
- **Compression is irreversible after save.** A committed node ("Lesbarkeit geprüft") drops its
  source on save → re-compress/reset blocked, dropdown shows „bereits komprimiert (keine Quelle)".
- **File lock has no graphical toggle** — single-writer locking is env-gated (`BELEG_FILE_LOCK=1`),
  off by default; no autosave/recover of unsaved changes, no read-only fallback when in use.
- **PDF-Tool edits add to the PDF; they don't rewrite its original text.** The second surface (a
  `.pdf` or a node binding opens it) can now **add text (FreeText / typewriter) and fill AcroForms**,
  saved back into the node via `saveDocument()` → `save_node_back` → `SetNodeBytes`. Self-authored
  text **round-trips** — reopening the node reloads it as editable FreeText. Limits: it can't edit/reflow
  the *original* body text of a PDF (a PDF stores positioned glyphs, not paragraphs — overlay only);
  **OCR / page-rearrange / compression from this surface, and signing, are not wired yet**. ⚠ **Compression
  flattens annotations** — compressing a node rasterizes the page, so any added text/forms become pixels
  and stop being editable (acceptable: compression is an explicit, deliberate flatten). See
  [`docs/pdf-tool.md`](docs/pdf-tool.md) for the roadmap.
- **Nested containers are recursed, but bounded** *(since 2026-06-26, Open items #12)* — a
  `.zip`/`.tar`/`.tgz`/`.eml`/`.msg` inside another container is extracted into a sub-folder.
  Accepted bounds: recursion stops at **`_ARCHIVE_MAX_DEPTH = 3`** (a deeper container shows
  „… zu tief verschachtelt"); the bomb budget is **shared across levels**, so when it is exhausted
  mid-way a still-unread inner container degrades to „nicht importierbar" and **its already-decoded
  children are not kept** (the whole inner container is dropped, never the import).
- **No direct Outlook drag-and-drop** — Outlook hands items over as OLE virtual files; import a
  `.msg`/`.eml` instead. No automatic DATEV check-in on document close (manual re-import in DATEV).
- **Multicore rasterization is GIL-limited (~1.2× on 4 threads)** — thread parallelism buys
  fairness/preemption, not throughput; true multicore would need a process pool (deferred).
- **Variants grow the file** — computed compression variants are embedded in the `.belegtool`
  (no sidecar). Split parts in **already-saved** files keep the old `no_compression` flag until
  re-split.
- **DATEV mode (v3.10.0) — accepted bounds.** Off by default; **write-back only succeeds when the
  document was opened from a DATEV checkout path and still byte-matches the server file** — a
  reopened `.belegtool` (or any structural transform) safely reports `conflict_content` and
  falls back to a local save (never a blind overwrite). DokAb keeps **no revision**, so the
  write is a permanent overwrite (guarded; a local backup is written first). The **file-to-DATEV
  placement** asks only for the Mandant number — domain/folder/register default (no graphical
  folder picker yet). Live behaviour is verified only by the human `manual_tests/10_datev.md`
  (no DATEVconnect in CI). The DATEVconnect OpenAPI specs in `import/` are **vendor IP —
  gitignored, never committed**.

> *Fixed 2026-06-18:* the keyboard-only context-menu bug (keyboard selection didn't arm the ▤ Menu /
> Shift+F10 key) — the primary row now takes DOM focus on selection ([`Tree.jsx`](webui/src/Tree.jsx)),
> and `onContextMenu` anchors at the row rect when the key supplies no pointer coords. Covered by
> `Tree.test.jsx` (focus moves to primary; input focus not stolen; coordless contextmenu still opens).

---

## Open / deferred items

### Next version — planned features (2026-06-08)
Captured from a planning pass; **not yet built.** Items 2–6 are real UI features (→ a MINOR
bump, **v3.10.0**), distinct from the already-staged **v3.9.4** work (committed-node
split/rotate/merge fixes, Elvish languages, Office unit tests, dep bumps, the Python-3.13
build, the MotW/UPX hardening — all on `master`, validated; **3.13 build + smoke-launch
passed 2026-06-08**). Suggested sequencing: **ship v3.9.4 first** (ready), then build these
as **v3.10.0**.

1. **Golden Office conversion test. — DONE (2026-06-13).** Implemented in
   [`tests/test_office_golden.py`](tests/test_office_golden.py): for each fixture in
   `tests/data/input/` (`golden_word.docx`/`golden_excel.xlsx`/`golden_ppt.pptx` +
   `golden_text.odt`/`golden_sheet.ods`/`golden_pres.odp`) it runs `office_via_com` and asserts
   **structurally** — valid `%PDF`, exactly 1 page, and a per-file sentinel survives into the
   rendered PDF text (not byte-equality; Office output isn't deterministic). The fixtures are
   self-authored (copyright ours), single-page, sentinel-bearing, with **no external references**
   (so the `.rels` scan never refuses them), generated by
   [`tests/make_office_fixtures.py`](tests/make_office_fixtures.py) (one-time; needs
   `python-docx openpyxl python-pptx odfpy`) and committed. **Runs in the default `pytest` suite**
   (per the 2026-06-13 decision — overriding the original "package-test only" plan); marked
   `office`, auto-skips on non-Windows / where the app isn't installed, opt out with
   `pytest -m "not office"`. **All 3 ODF formats now verified converting on a real Office
   machine** (no longer mocked-COM only). Storing golden *PDFs* in `tests/data/expected/` was
   dropped as redundant — the comparison is structural, and stored Office PDFs aren't
   deterministic.
2. **Toolbar redesign — smaller icon buttons. — DONE (2026-06-27).** [`Toolbar.jsx`](webui/src/Toolbar.jsx)
   is now icon-only: every button drops its visible label, the text moves into the `title`
   tooltip, and each carries an `aria-label` so screen readers and role/name queries keep the
   full name. Export shows the selection count as a `.count-badge`; the Save split-button's main
   part is icon-only with a dirty dot. Compact square buttons via `.tb-btn` in `App.css`. Tests
   that clicked toolbar buttons by visible text now query by role+name; `Toolbar.test.jsx` locks
   every icon's accessible name.
3. **„Speichern" as a split-button. — DONE (2026-06-26).** The toolbar's two Save buttons are now
   one split-button ([`SaveSplitButton.jsx`](webui/src/SaveSplitButton.jsx)): the main part saves in
   place (shows the dirty „•"), a caret opens a small dropdown with **„Speichern unter…"**.
   Accessible: `aria-haspopup`/`aria-expanded`, `role="menu"`/`menuitem`, closes on Escape and
   outside-click, focus moves to the item on open. Covered by `SaveSplitButton.test.jsx` (8).
   New i18n key `Weitere Speicheroptionen` (en done; others via PENDING_TRANSLATIONS batch).
   **Note:** the dropdown now uses the **shared menu hook of #10** ([`hooks/useMenu.js`](webui/src/hooks/useMenu.js)).
4. **Rotate controls — swap display order. — DONE (v3.10.0).** [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)
   now renders the rotate buttons **left-then-right** (↺ before ↻); locked by `PreviewControls.test.jsx`.
5. **Cross-window drag-and-drop (copy by default).** Drag a node out of one BelegTool window
   into **another** → **copy** by default (source keeps its node). Distinct from the Outlook
   drag-in (still won't-do; OLE virtual files).
   Both windows share **one in-process `CoreApi`**, so the **data** transfer is trivial
   in-engine; the only hard part is the cross-window **gesture**.
   A web drag can't cross two separate WebView2 windows (window B gets no events from A's drag),
   so we avoid a cross-window drag entirely.
   All three candidate designs keep the drag **intra-window** (so the WebView2 cross-window limit
   never applies); shared/source contents come from the shared `CoreApi`.
   **Decision (2026-06-09): build (A) in v3.10.0; (B) and (C) are logged for later versions.**
   **Revised (2026-06-27): (A) is CUT from v3.10.0 — not built; the in-app DATEV integration was
   prioritised for v3.10.0 instead. (A)/(B)/(C) are all deferred to a later version.**
   - **(A) „Austausch-Pad" (interchange tray) — deferred (was: NOW).** A small shared tray in every window. Drag a
     node *onto the pad* (same-window drag) → `CoreApi` stages the subtree; the pad shows in every
     window (shared `CoreApi`); drag the item *from the pad onto a tree* (same-window drag) → copy
     inserted (`materialize_subset` → insert). Simple; **copy-only**; doubles as a within-window
     clipboard. Needs a focus/poll refresh of the pad (no cross-window event bus).
   - **(B) Second tree-pane (dual-pane) — later.** A second tree view in the same window loading
     another open document; drag between panes → move or copy. Richer "merge two documents" UX;
     costs cross-document `CopyAcross`/`MoveAcross` + source-window refresh on move.
   - **(C) „Super-Tree" view — later.** A toggle that morphs the current window into a synthetic
     tree whose first-order folder-nodes are **all open documents**, each document's tree as its
     children (toggle back to the normal single-doc view). **MVP: only the current document is
     editable; the others are read-only sources** — drag a foreign node into the current doc →
     copy. *Feasibility (checked):* builds naturally on the existing **virtual-view machinery**
     (the filtered/group views are already read-only synthetic trees with an edit-lock). Needs:
     assemble the super-tree from all open sessions; **namespaced node ids** (which doc a node
     belongs to); the cross-doc copy op (shared with B); and the read-only gate on foreign
     subtrees. Cleanest UX (one unified tree of everything open) and most ambitious; a later step
     could allow full cross-doc move/edit (with multi-document save semantics).
   A true OS-drag drop directly between windows remains an optional native upgrade in any case.
6. **Insert + edit a page (text editor) — via node attributes, NOT a new node kind.** Add two
   persisted fields to the node / PDFNode (round-trip in `.belegtool`):
   - **`editor_based`** (bool) — this node was built from text and can be switched back to editing;
   - **`editor_text`** (str) — its source text.
   "Insert blank page" = a node with `editor_based=True`, `editor_text=""`. The UI shows an editor
   pane **only when `editor_based`**; on commit, **rebuild the PDF page(s) from `editor_text`**
   (text→PDF, e.g. reportlab) and replace the node's bytes.
   ⚠ **The page count can change on rebuild** (more text → more pages): recompute `pdf_length`
   and propagate it — TOC page numbers, folder aggregate counts, the windowed render-cache
   version token, and export offsets all depend on it. **Decided (2026-06-08):** **compress is
   disabled** on an editor node (the text is the source of truth, the rendered PDF is tiny);
   **rotate/split/merge drop editor mode** — the result becomes a plain rebuilt PDF
   (`editor_based=False`), avoiding "rebuild un-rotates the page" surprises. Plain-text first;
   rich text later if wanted.
7. **Multi-select tagging. — DONE (2026-06-26).** When **more than one node is selected**, the tag
   editor applies/removes a tag across **all** of them as one undo step via a new
   **`TagMany(node_ids, tag, add)`** command ([`core/commands.py`](core/commands.py)) — it adds or
   removes ONE tag per node, keeping each node's other tags (ids de-duped, missing ids skipped,
   empty tag a no-op). Single-select still uses `SetTags` (whole-set replace) unchanged. The editor
   ([`TagEditor.jsx`](webui/src/TagEditor.jsx)) shows the **union** of the selected nodes' tags with
   a count badge; a tag not on every node is **partial** (`te-chip-partial`, hollow) and re-adding it
   completes it across the selection. Pure union logic in
   [`lib/tags.js`](webui/src/lib/tags.js) (`tagSelectionState`/`tagsOnAll`). Tests:
   `tests/test_tag_many.py` (8), `lib/tags.test.js` (+5), `TagEditor.test.jsx` (+5). New i18n key
   `{n} markiert` (en done; other languages via PENDING_TRANSLATIONS batch).
8. **„Neuer Ordner" — insert at the selection + naming dialog. — DONE (v3.10.0).** The toolbar
   „Ordner" button now creates the folder **inside a selected folder / as a sibling after a
   selected leaf / at the root** (pure `newFolderTarget` in [`lib/tree.js`](webui/src/lib/tree.js),
   unit-tested) and opens a **naming dialog** (default „Neuer Ordner" pre-filled) first. Wiring
   covered by `App.addfolder.test.jsx`.
9. **Zoom should keep the document position, not the viewframe position. — DONE (v3.10.0).**
   [`Preview.jsx`](webui/src/Preview.jsx) lays pages out at `width = 560 * zoom`, so page heights
   scale with zoom. It now captures a **logical anchor** (visible page index + intra-page fraction
   at the viewport top) every scroll/relayout frame and re-applies it in a `useLayoutEffect([zoom])`
   after the relayout, so the document position at the viewport top stays put. Anchor math is the
   pure [`lib/zoomAnchor.js`](webui/src/lib/zoomAnchor.js) (`pageFraction` / `scrollForAnchor`),
   unit-tested in `lib/zoomAnchor.test.js`; the visual behaviour is covered by `manual_tests`
   MT-10 (jsdom has no layout, so the integration is verified by hand).
10. **Reusable accessible menu (keyboard nav). — DONE (2026-06-27).** The shared menu contract now
    lives in [`hooks/useMenu.js`](webui/src/hooks/useMenu.js): `rovingFocusKeydown` (↑/↓ cycle,
    Home/End jump), `tagMenuItems` (role="menuitem" tagging), and `useMenuDismiss` (Escape +
    outside-mousedown close while open). Both **`ContextMenu.jsx`** (roving focus + tagging) and the
    **`SaveSplitButton.jsx`** dropdown (dismiss + roving focus) use it — duplication removed.
    ContextMenu keeps its context-specific backdrop, Escape-via-window listener and viewport
    clamping. Covered by `hooks/useMenu.test.jsx` (7) plus the existing ContextMenu/SaveSplitButton
    suites. Enter/Space activate the focused `<button>` natively.
11. **Error-code contract (architectural, optional).** *(Deferred audit High — the pragmatic
    `lib/messages.js` reverse-template localizer already covers it functionally.)* Optionally
    replace backend German error strings with stable **`{ code, params }`** so the UI owns all
    wording (kills the reverse-template matching). If not done, **new error paths from #1/#5/#6
    must follow the established convention**: raise the static German text as an `en.js` key (+
    full-coverage langs, bump the key-lock), and add a `messages.js` template for any dynamic parts.
12. **Nested archive *and mail* extraction. — DONE (2026-06-26).** A `.zip`/`.tar`/`.tgz` **or a
    `.msg`/`.eml`** nested *inside* another container is now **recursed** into a FOLDER of its
    extracted members instead of degrading to „nicht importierbar". `archives._member_result` /
    `_extract_nested` route an inner container back through the matching `extract_*` (cross-kind:
    a `.msg` in a `.zip`, a `.zip` attached to an `.eml`, …), preserving the tree
    (archive → mail → attachment). Recursion is bounded by **`_ARCHIVE_MAX_DEPTH = 3`** (anti
    zip-quine → „zu tief verschachtelt"), and the bomb caps are now a **shared `_Budget`** (decoded
    bytes + member count) threaded through every level, so nesting can't compound past
    `infra.limits.BOMB_CAP_BYTES`/`BOMB_CAP_ENTRIES`. A corrupt/oversized inner container degrades to
    „nicht importierbar" without aborting the import. Tests: `tests/test_archive_nested.py` (9 cases:
    cross-kind recursion, depth bound, shared byte+member budget, corrupt-nested degrade); existing
    `test_archive_*` unchanged. (Logged from the 2026-06-16 audit, finding #6; extended to nested
    mail 2026-06-26.)
    **Follow-up (2026-06-26): archive subfolders are now honored as folder nodes.** A zip/tar
    member path like `rechnungen/2024/beleg.pdf` builds `Ordner rechnungen › Ordner 2024 ›
    beleg.pdf` (helpers `_split_member_path`/`_ensure_folder`/`_insert_by_path` in `archives.py`),
    merging siblings under shared folders — fixing the old zip **path-in-the-leaf-name** and the tar
    **basename-flatten** (which also dropped same-named files in different folders). Composes with
    the nesting above (a container at `sub/inner.zip` → `Ordner sub › Ordner inner.zip › …`). Tests:
    `tests/test_archive_subfolders.py` (6).
13. **Configurable export split. — DONE (2026-06-26).** The export dialog
    ([`ExportDialog.jsx`](webui/src/ExportDialog.jsx)) gained **„In mehrere Dateien aufteilen"** with a
    page **threshold** (`split_pages`, default 100; off = single PDF) and a **break level**
    (`split_level`), asked at export time:
    - **„oberste Ordner"** (`top`) — split only between top-level items; a top folder is never split.
    - **„jeder Ordnergrenze"** (`folder`) — a large folder is split across parts at child boundaries;
      a leaf is never split.
    - **„mitten im Dokument"** (`page`) — a strict page-count cut that may split a single document
      across files (the part name carries the original page range, e.g. `Rechnung (S. 1–3)`).
    A shared grouping engine in [`toc_export.py`](formats/toc_export.py) — `_pack_units`,
    `_leaves_with_path`, `_subtree_from_leaves`, `_subtree_from_pages`, `_slice_leaf`, `_plan_groups` —
    packs atomic units (top-node / leaf / page) into ≤-threshold parts and rebuilds a pruned forest
    per part; the existing cross-reference TOC assembly (`export_pdf_split_with_toc`) renders each.
    `CoreApi.export` dispatches on `split_pages`/`split_level` and returns `paths` (the UI reports the
    file count). Tests: `tests/test_export_split.py`, split cases in `tests/test_core_api.py`,
    `ExportDialog.test.jsx`. i18n for all 7 new labels done across the full-coverage languages.

### Build hygiene — embed the version resource in BelegTool.exe (noted 2026-06-25)

The PyInstaller onedir **`BelegTool.exe` carries no Windows version resource** — Properties →
Details shows blank ProductVersion/FileVersion, and fleet recon / `Get-Item …VersionInfo`
reads nothing; the version is only tracked via `version_info.py` and the machine-wide
installer's Programs & Features entry. **Future builds should embed it:** generate a
PyInstaller `version_info.txt` (`VSVersionInfo`) from `version_info.VERSION` and reference it
in `belegtool.spec` via `EXE(…, version='version_info.txt')`, so the exe self-reports its
version (helps support, fleet inventory, and RDS deploys that key on the file version).
Surfaced 2026-06-25 verifying the RDS install (read v3.9.4 from P&F, but the exe reported no
embedded version). Low effort; do it on the next build bump.

### Planned work — sequenced (decided 2026-06-07)
**Order: (1) update-checker, then (2) file lock.** Both deferred for now; recorded so the design survives the gap.

1. **Update-checker ("Update available") — deferred, design fixed.** Inform the user when a
   newer release exists; do **not** auto-install.
   - **Privacy rule (hard): never check for updates without asking.** No silent phone-home.
   - **First approach: the user must *request* a check** — a manual "Nach Updates suchen"
     button/menu item. An automatic startup check, if ever added, is **opt-in only** behind a
     first-run consent toggle (DSGVO: the check discloses IP/usage to the update host).
   - Mechanism: `GET …/releases/latest` (GitHub API) → compare `tag_name` vs
     `version_info.VERSION` (semver); newer → show a badge linking to the release page
     (browser download + manual unzip-replace, matching today's install flow).
   - Architecture (logic/UI split): pure `services/updates.py` (`is_newer`, `parse_release`,
     UI-free, unit-tested with canned JSON) + an injectable fetch port in `infra` (stdlib
     `urllib`, offline fails silently) + `HostApi.check_for_update()` + a React badge/button.
   - Later: move the source to a self-hosted `latest.json` on the GitHub Pages homepage
     (no rate limit; phased rollout; `mandatory`/yanked flags). Production auto-download/
     install (WinSparkle/Inno/MSIX) is **gated on code signing** — not before.

2. **Exclusive file lock (single-writer) — SHIPPED in v3.9.0 (off by default).** See the
   **File lock** section below. (Built ahead of the updater after all.) Still deferred within
   it: a graphical on/off setting (currently env-gated), the Office-style autosave/recover
   sidecar, and the read-only fallback.

- **Accepted audit-info residuals (2026-06-12, deliberately not fixed):**
  `save()` reads `_locks`/`_paths` outside the lock (unreachable via the modal UI);
  `SetPeriod` does no value validation; `office_via_com`'s
  CoInitialize/CoUninitialize balance on js threads is best-effort;
  `_friendly_import_error`'s raw-text fallback tail stays untranslated (known);
  the OOXML `.rels` pre-scan does not cover legacy OLE `.doc/.xls/.ppt` (no ZIP —
  COM guards only; fail-open is deliberate there);
  `_last_seed` is written unlocked (atomic tuple swap, annotated in code);
  a `_count_for` insert racing `close_session` can re-add a just-pruned `_pcount`
  key (one int); `render_compressed_window`/`page_count` don't touch the view dir
  (any visible page goes through `render_window`); `CoreApi.render` is kept for the
  named-pipe IPC server and `CoreApi.render_compressed` for tests (both annotated;
  their dead JS-bridge wrappers in `host.py` were removed 2026-06-12).
- **Manual tests 01–04 rewritten against the React UI (2026-06-15)** — the legacy
  Tk menu/toolbar wording was removed; 01–08 now all describe the React/pywebview UI.
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

### Probably won't be done (accepted limitations)
- **Automatic DATEV check-in on close** — *not feasible* and won't be pursued. With the file
  lock, DATEV now *detects* the file changed, but it does not auto re-import (check in) when
  the document closes. Acrobat is single-instance, so DATEV keys on a **document-level** signal
  (file-handle release and/or Acrobat's legacy **DDE** server) that a generic editor can't
  reliably reproduce; `.belegtool` is also not a DATEV-configured editable type. Workaround:
  check the document back in **manually** in DATEV after editing. Re-import via the
  **DATEVconnect DMS API** would be a separate, heavyweight integration (not planned).
- **macOS / Linux** — Windows-only (PyInstaller `win64`; Edge WebView2 GUI; hard `pywin32`/
  `pythonnet` deps; COM Office import). The PDF core is cross-platform, so a port is feasible
  but not maintainer-planned — opened up as a **community contribution** via the draft RFC
  [`docs/cross-platform-port.md`](docs/cross-platform-port.md) (linked from `CONTRIBUTING.md`).
- **Direct drag-and-drop from Outlook** — dragging a mail/attachment straight out of Outlook
  into the window does **not** work and likely won't. Outlook hands items over as OLE
  *virtual files* (`CF_FILEGROUPDESCRIPTOR` + `CF_FILECONTENTS`); the WebView2/HTML drop layer
  only sees real files (`dataTransfer.files` is empty for Outlook drags), so
  [`useOsFileDrop`](webui/src/hooks/useOsFileDrop.js) ignores them. Supported instead:
  **Import (📥) a `.msg`/`.eml`**, or drag the Outlook item to a folder/desktop first (which
  creates a `.msg`) and drag/import that. True support would need a native Win32 `IDropTarget`
  reading the OLE formats and feeding `import_bytes` — Windows-only, fiddly to bolt onto the
  WebView2-hosted window; not planned.

---

## UI conventions
- React + Vite SPA in `webui/`; rendered inside the pywebview host
- Toolbar: open/import/save/export/new-window/undo/redo ([`App.jsx`](webui/src/App.jsx))
- Tree + drag-and-drop in [`Tree.jsx`](webui/src/Tree.jsx); right-click ops in [`ContextMenu.jsx`](webui/src/ContextMenu.jsx)
- Compression controls (method dropdown incl. `jpg_color`, DPI, apply/reset) in [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)

### Internationalization (i18n)

Source-string i18n in [`webui/src/i18n/`](webui/src/i18n/): German is the source (the literal
`t('…')` key), [`en.js`](webui/src/i18n/en.js) is the **canonical full key set** (151 keys =
124 UI strings + 13 backend command-error messages + 14 host-level error/warning
strings; locked by `i18n.test.js`, which also asserts every full-coverage language's
key set == `en`'s), every other
language maps German→target and **falls back to the German source** for any missing key.
`translate()`/`resolveInitialLang()` in [`index.js`](webui/src/i18n/index.js); the picker
renders `LANGUAGE_NAMES`.

- **Batch-translate policy (2026-06-26):** to keep UI feature work from being blocked on ~18
  language files per string, **new UI strings ship in de (source) + en only**; the other
  full-coverage languages are translated **later, in one batch**. The mechanism is a
  **`PENDING_TRANSLATIONS`** set in [`i18n.test.js`](webui/src/i18n/i18n.test.js): a key listed
  there must exist in `en.js` (still enforced — never ship an untranslated `t()`), but is
  **exempt from the full-coverage assertion** until translated. Workflow: (1) add the German
  `t()` literal, (2) add the `en.js` entry **and bump the en key-count**, (3) add the key to
  `PENDING_TRANSLATIONS`. The batch pass translates them into every language and **empties the
  pending set**. Until a key falls back to German in the untranslated languages, which is
  acceptable in the interim.

- **Localized errors (2026-06-08):** core `CommandError` messages are raised in **German**
  (the source language) and surfaced via `t(error)` in [`App.jsx`](webui/src/App.jsx), so they
  localize like any other string. The 13 user-facing command errors are translated in all
  full-coverage languages; internal/developer errors (`unknown session`, `node not found: …`,
  invalid direction/status, …) deliberately stay English diagnostics.
- **Localized host-level errors (2026-06-10):** `CoreApi`'s static error/warning strings
  (lock "in use", "nichts zu exportieren/angezeigt/importiert", …) and `host.py`'s
  "Fenster nicht gefunden" are en.js keys too;
  messages with **dynamic parts** (`_friendly_import_error` per-file errors, "ungültige
  Daten: …", the export skip warning, App's "Teilweise importiert — …" composite) are
  reverse-matched against German templates in
  [`webui/src/lib/messages.js`](webui/src/lib/messages.js) (`localizeMessage`) so the static
  wording translates while filenames/exception text survive. `messages.test.js` locks the
  templates against `core/api.py`/`App.jsx` — changing those backend strings requires
  updating the templates + all full-coverage language files.

- **Regional English (2026-06-07):** the generic `en` code was split into **`en-US`
  ("English (US)")** and **`en-GB` ("English (UK)")**, each a thin spelling-override of the
  `en` base ([`en-US.js`](webui/src/i18n/en-US.js) overrides favorite/favourite trio only —
  the `en` base already uses `color`/`grayscale`; [`en-GB.js`](webui/src/i18n/en-GB.js)
  overrides favourite/colour/greyscale). `resolveInitialLang`
  maps a legacy/generic `en` (stored or `navigator.language`) → `en-US`, and matches an exact
  browser locale (`en-GB`) before the 2-letter fallback. **`en.js` stays as the base/coverage
  reference — don't register it as a selectable language.**
- **Completeness (2026-06-08):** **19 languages are 100% (all 151 keys, incl. error messages)** — de (source),
  en-US, en-GB, fr, es, ca, ru, uk, hr, ko (professional), la (scholarly Latin), mnn (Minionese
  joke), the German dialects bar/nds/vie, and the Celtic + Yiddish best-effort cy/ga/gd/yi
  (**native review still welcome** — see each file's header). Intentional **partials** (only
  terms with a real attested word; the rest falls back to German rather than inventing nonsense):
  **tlh** (Klingon) and the Elvish **qya** (Quenya) / **sjn** (Sindarin). For the Store listing,
  advertise **de + en-US/en-GB** (verifiable as native-professional) — the rest ship as a
  best-effort bonus that falls back gracefully.
- The **Help modal** content ([`help/content.js`](webui/src/help/content.js)) is separate from
  UI strings: DE + EN authored (🇩🇪/🇬🇧 flag toggle), others best-effort, unknown → EN fallback
  (`helpFor()`), so `en-US`/`en-GB` UIs correctly show the English help.

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
- **Version `3.10.0`** (bug form default + BETA_TESTING heading) → bump when `version_info.py` changes.
- **Windows 10/11 only**; **Office-via-COM** caveat for Word/Excel/PPT import.
- **One known gap that must NOT be reported as a bug** (the bug form's required
  checkbox enforces this): compression irreversible after save ("bereits komprimiert
  (keine Quelle)"). The former auto-split gap was removed when #13 (configurable
  export split) shipped on the v3.10 branch. **If this gap is fixed, remove it from
  the checkbox, BETA_TESTING.md §4, and CONTRIBUTING.md** — otherwise testers are
  told a working feature is broken.
- **Manual tests `01`–`08` are all current against the React UI** (01–04 rewritten
  2026-06-15; the removed Tk GUI is no longer referenced anywhere).
- **Two run paths** (prebuilt onedir folder; from source: Python 3.12+ + Node, `pip
  install -r requirements.txt`, `cd webui && npm install && npm run build`, `python
  host.py`) and **no published Release yet** — update BETA_TESTING.md §1 once a
  Release/installer exists.
- **Fixtures in `tests/data/input/`** (regen `python tests/make_fixtures.py`).
- The `config.yml` and template links hardcode the repo URL
  `tobiasheinrichfaska/DigitalerUnterlagenOrdner` and the `master` branch.

⚠️ **Manual GitHub steps (not in the repo):** Discussions must be enabled in repo
**Settings → Features**, and a Release published (or the build folder zipped) for
the prebuilt download path to work.
