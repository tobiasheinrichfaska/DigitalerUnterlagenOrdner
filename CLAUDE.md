# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: **React + Vite SPA inside a pywebview host** (Edge WebView2). Version: **3.9.3**.

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
`infra/` = ports (tasks, log_config, tools); `host.py`/`version_info.py` =
entry/config; `webui/` = React frontend (`src/lib/` holds its UI-free logic).

### Entry point & host

| File | Role |
|---|---|
| `host.py` | **The single entry point.** pywebview host: one shared `CoreApi`, one `HostApi` **per window** (bound to the window uid). Native dialogs, `new_window`, per-window close guard (`window.__belegDirty`), startup `_prewarm` of the heavy PDF libs. |

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
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.9.3) |
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

**Run:** dev — `cd webui && npm run dev` then `set BELEG_DEV=1 && python host.py`;
prod — `cd webui && npm run build` then `python host.py`. **Unit tests:** `cd webui
&& npm test` (Vitest + jsdom; `src/lib/core.test.js` smoke-tests the `core.js` bridge —
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
parser could otherwise resolve a target our `zipfile` couldn't read). Only genuine
non-zip legacy OLE `.doc/.xls/.ppt` stays fail-open — no `.rels` exists, there only
the COM guards apply. Office apps are `Quit()` in `finally`, so a
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
  the decision is **baked at save** (`CoreApi._bake_no_gain`), round-trips in the `.belegtool`,
  and is **cleared on rotate**. So a "nothing smaller" node is not re-evaluated on load and
  shows no red dot. Auto-compute on view skips these.
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

Current tag: **v3.9.3** (beta)

---

## Open / deferred items

### Next version — planned features (2026-06-08)
Captured from a planning pass; **not yet built.** Items 2–6 are real UI features (→ a MINOR
bump, **v3.10.0**), distinct from the already-staged **v3.9.4** work (committed-node
split/rotate/merge fixes, Elvish languages, Office unit tests, dep bumps, the Python-3.13
build, the MotW/UPX hardening — all on `master`, validated; **3.13 build + smoke-launch
passed 2026-06-08**). Suggested sequencing: **ship v3.9.4 first** (ready), then build these
as **v3.10.0**.

1. **Golden Office conversion test.** *You* provide one reference Word/Excel/PowerPoint file;
   each is run through `office_via_com` while testing the package; the **first output PDFs are
   approved once → promoted to `tests/data/expected/`** as golden. Later runs compare
   **structurally** (valid PDF + page count + key text), **not** byte-equality (Office output
   isn't deterministic). A live/manual test (needs real Office), triggered at package-test
   time — not in the default unit suite.
2. **Toolbar redesign — smaller icon buttons.** Shrink the toolbar to compact, recognisable
   icons for Open / Import / Help / Save (+ Export, New window, Undo/Redo). Tooltips carry the
   text labels; keep an `aria-label` per button.
3. **„Speichern" as a split-button.** A normal click saves in place; a small dropdown caret on
   the same button opens a menu with **„Speichern unter…"**. **Decided:** build the split-button
   and evaluate it in use.
4. **Rotate controls — swap display order.** In [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)
   reorder the two rotate buttons to **left-then-right** (currently right before left).
5. **Cross-window drag-and-drop (copy by default).** Drag a node out of one BelegTool window
   into **another** → **copy** by default (source keeps its node). Distinct from the Outlook
   drag-in (still won't-do; OLE virtual files).
   Both windows share **one in-process `CoreApi`**, so the **data** transfer is trivial
   in-engine; the only hard part is the cross-window **gesture**.
   A web drag can't cross two separate WebView2 windows (window B gets no events from A's drag),
   so we avoid a cross-window drag entirely.
   All three candidate designs keep the drag **intra-window** (so the WebView2 cross-window limit
   never applies); shared/source contents come from the shared `CoreApi`.
   **Decision (2026-06-09): build (A) now (v3.10.0); (B) and (C) are logged for later versions.**
   - **(A) „Austausch-Pad" (interchange tray) — NOW.** A small shared tray in every window. Drag a
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
7. **Multi-select tagging.** When **more than one node is selected**, applying/removing a tag
   should affect **all selected nodes** (today the tag editor acts on the single context-menu
   node). Apply over `selectedIds` (resolve folder/child overlaps like the other multi-ops) as
   one undoable step.
8. **„Neuer Ordner" — insert at the selection + naming dialog.** New folder should be created
   **at the selected node's position / parent**, not always at the root; and it should open a
   **naming dialog** first (default name pre-filled) instead of creating an unnamed folder.
9. **Zoom should keep the document position, not the viewframe position.** *(Finding from a
   check — current behaviour:)* the preview lays pages out at `width = 560 * zoom`
   ([`Preview.jsx`](webui/src/Preview.jsx)), so page heights scale with zoom, but **`scrollTop`
   is not re-anchored** (no effect depends on `zoom`). Result: the pixel scroll position stays
   fixed → the **document position drifts** when zooming while scrolled down (top-anchored zoom
   is fine). Fix: before changing zoom, capture the anchor (visible page index + intra-page
   fraction at the viewport top, or `scrollTop/scrollHeight`) and reapply it after the relayout.
10. **Reusable accessible menu (keyboard nav).** *(Deferred audit item, folded here.)* Build one
    accessible-menu pattern — `role="menu"`/`menuitem`, roving focus, ↑/↓ to move, Enter/Space to
    activate, Esc to close, focus-first-on-open — and have **`ContextMenu.jsx` AND the planned #3
    Save split-button dropdown share it**, rather than retrofitting today's ContextMenu and
    rebuilding for the split-button. (Today: ContextMenu is mouse + Esc/backdrop only.)
11. **Error-code contract (architectural, optional).** *(Deferred audit High — the pragmatic
    `lib/messages.js` reverse-template localizer already covers it functionally.)* Optionally
    replace backend German error strings with stable **`{ code, params }`** so the UI owns all
    wording (kills the reverse-template matching). If not done, **new error paths from #1/#5/#6
    must follow the established convention**: raise the static German text as an `en.js` key (+
    full-coverage langs, bump the key-lock), and add a `messages.js` template for any dynamic parts.

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
  `SetPeriod` does no value validation; `initialize_async`/`office_via_com`
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
  `en` base ([`en-US.js`](webui/src/i18n/en-US.js) favorite/color/grayscale;
  [`en-GB.js`](webui/src/i18n/en-GB.js) favourite/colour/greyscale). `resolveInitialLang`
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
- **Version `3.9.3`** (bug form default + BETA_TESTING heading) → bump when `version_info.py` changes.
- **Windows 10/11 only**; **Office-via-COM** caveat for Word/Excel/PPT import.
- **Two known gaps that must NOT be reported as bugs** (the bug form's required
  checkbox enforces this): (1) export >100 pages → single PDF, auto-split not wired
  into the UI; (2) compression irreversible after save ("bereits komprimiert (keine
  Quelle)"). **If either gap is fixed, remove it from the checkbox, BETA_TESTING.md
  §4, and CONTRIBUTING.md** — otherwise testers are told a working feature is broken.
- **Manual tests `05`–`07` are current; `01`–`04` are stale (removed Tk GUI).** When
  01–04 are rewritten against the React UI, drop the "stale" wording everywhere it
  appears (BETA_TESTING.md §3, CONTRIBUTING.md, `manual_tests/README.md`).
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
