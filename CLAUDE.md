# CLAUDE.md — DigitalerUnterlagenOrdner (BelegTool)

> Workspace-wide conventions (language, git, build, collaboration): [`c:\skripte\private\general stuff\CLAUDE.md`](../../private/general%20stuff/CLAUDE.md)

---

## Project overview

Desktop application for hierarchical management, preview, and export of PDF documents and receipts. Platform: Windows. UI: **React + Vite SPA inside a pywebview host** (Edge WebView2). Version: **3.11.4**.

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
`datev/` = the lazy DATEVconnect integration (now the separable package `packages/datev-dokab/`, see below; DATEV-mode only; never imported when
off — `inapp`, `client`, `writeback`, `provenance`, `config`, `transport`, `types`,
`endpoints` (URL builder), `synthetic_pdf` (probe/test PDF); the research tool `probe_gui` lives in `tools/datev_probe/`);
`infra/` = ports + per-user state (tasks, log_config, tools, `limits.py` re-export, `settings.py`,
`file_lock.py`, `window_geometry.py`); `host.py`/`version_info.py` =
entry/config; `webui/` = React frontend (`src/lib/` holds its UI-free logic).

### Entry point & host

| File | Role |
|---|---|
| `host.py` | **The single entry point.** pywebview host: one shared `CoreApi`, one `HostApi` **per window** (bound to the window uid). Native dialogs, `new_window`, per-window close guard (`window.__belegDirty`), startup `_prewarm` of the heavy PDF libs. The **first** window **persists its geometry** (size/position/monitor) to `%APPDATA%\…\window.json` on close and restores it on next launch; a saved geometry whose monitor is gone falls back to the default (validated by the pure [`infra/window_geometry.py`](infra/window_geometry.py), tested). |

### The three separable libraries live in their own public repos (since 2026-11-27)

⚠️ **`packages/` no longer exists in this repo.** `datev-dokab`, `belegtool-archives` and `belegtool-compress` were extracted with
their full history (`git filter-repo --subdirectory-filter`) into
[`tobiasheinrichfaska/datev-dokab`](https://github.com/tobiasheinrichfaska/datev-dokab),
[`…/belegtool-archives`](https://github.com/tobiasheinrichfaska/belegtool-archives) and
[`…/belegtool-compress`](https://github.com/tobiasheinrichfaska/belegtool-compress) (tag `v0.1.0`, branch `main`).
`requirements.txt` pins them as `name @ git+https://github.com/tobiasheinrichfaska/<name>.git@v0.1.0` (non-editable; build needs git + network).
**Change flow:** edit + test in the package repo → tag → bump the tag in `requirements.txt` (and the CI job `raster-parity`) → re-run the
full gate here. For a local dev loop: `pip install -e <clone>` into `.build_venv`, then reinstall the pinned tag before committing.
Each package repo has its own CI (`.github/workflows/ci.yml`: ubuntu + windows, Python 3.13, pytest; green 2026-11-27). The host tests that
read package metadata (`tests/test_no_agpl_pdf_deps.py`) now use the installed distribution's metadata; the CLA-copy test
(`test_package_cla.py`) is gone — **the CLA exists in four `CONTRIBUTING.md` copies (this repo + the three packages); change them together by hand.**
SPDX: `scripts/add_spdx_headers.py` only covers this repo now. The sections below describe the packages' design; file paths
`packages/<name>/…` in them mean the root of the respective package repo.

### `packages/datev-dokab/` — separable DATEV library

`datev/` (import name stays `datev`) lives in `packages/datev-dokab/` with its own `pyproject.toml`
(AGPL-3.0-or-later, no dependencies), README, LICENSE and its internal tests (`packages/datev-dokab/tests/`;
`test_datev_coreapi`/`test_datev_provenance_roundtrip` stay in `tests/` because they need `core`). The main repo
installs it (non-editable) via `./packages/datev-dokab` in `requirements.txt`; `belegtool.spec` collects it as a
hidden import; CI has an isolated `datev-dokab` job. **Extraction** into its own repo needs no code change:
`git filter-repo --subdirectory-filter packages/datev-dokab`, tag `v0.1.0`, then switch `requirements.txt` to the
pip-git URL — steps in [`packages/datev-dokab/EXTRACTION.md`](https://github.com/tobiasheinrichfaska/datev-dokab). The package
must not import host modules (guarded by `test_datev_standalone.py`). Dev runs: re-run `pip install ./packages/datev-dokab`
after every change to it; a non-frozen `datev.config.json` is read from `DATEV_CONFIG_DIR` (never the CWD).

### `packages/belegtool-archives/` — separable container-extraction library

The container readers (ZIP/TAR/TGZ/EML/MSG extraction, nesting limits, bomb guards) and the shared caps
(`limits.py`) live in `packages/belegtool-archives/` (import name `belegtool_archives`; own `pyproject.toml`, AGPL-3.0-or-later,
no hard dependencies, README, LICENSE, `EXTRACTION.md`, tests in `packages/belegtool-archives/tests/`). **Boundary:** the package
never imports the host (`infra`/`core`/`formats`/`universal_importer`, guarded by `test_standalone.py`); logger
`logging.getLogger("belegtool_archives")`; member conversion (image/Office/HTML → PDF) is **injected** as
`convert_member(content: bytes, name: str) -> bytes | BytesIO` (default: only `.pdf` passes through).
`universal_importer/archives.py` is a thin shim that injects `UniversalImporter.convert`; `infra/limits.py` is a re-export
(`services/variant_blobs.py`/`infra/tools.py` unchanged). `.msg` is read by the package's OWN reader `msg_reader.py` (+ `rtf_deencap.py`) on `olefile` (BSD-2) + `compressed-rtf` (MIT),
extra `msg` (**2026-11-26: `extract-msg` GPLv3 + RTFDE LGPL removed completely** — see *Findings from 2026-10-18*, guard
`tests/test_no_gpl_msg_deps.py`); without the extra `.msg` degrades to „nicht importierbar". Body order HTML > HTML unwrapped from
encapsulated RTF > plain text as minimal HTML > raw `.rtf` (an ordinary RTF is not converted); an attached Outlook message is recursed.
Pinned by `tests/test_msg_parity.py` (written first against extract-msg) + `test_msg_reader.py`; **synthetic fixtures only**. Installed non-editable via
`./packages/belegtool-archives` in `requirements.txt`; `belegtool.spec` collects it as a hidden import; CI has an isolated
`belegtool-archives` job. Re-run `pip install ./packages/belegtool-archives` after every change to it. Extraction:
`git filter-repo --subdirectory-filter packages/belegtool-archives` (see its `EXTRACTION.md`). Host-side companions:
`tests/test_zip_member_guard_host.py`, `tests/test_limits.py`.

### `packages/belegtool-compress/` — separable PDF-compression library

`formats/compress_pdf_bytes.py` (render-based jpg/jpg_color/png + pikepdf variants, `CompressionConfig`, `CompressionCancelled`,
page-count truncation guard) and the CPU-fairness primitives (`services/cpu.py`: `worker_count`, below-normal threads, `SystemCpuSampler`,
RAM budget) live in `packages/belegtool-compress/` (import name `belegtool_compress`: `compress.py`, `cpu.py`, `pixels.py`, `raster.py`, `pdfinfo.py`; own
`pyproject.toml`, AGPL-3.0-or-later, deps pypdfium2/Pillow/pikepdf/pypdf (PyMuPDF only as `oracle`/`dev` extra), README, `EXTRACTION.md`, tests in
`packages/belegtool-compress/tests/`). **Boundary:** the package never imports the host nor `belegtool_archives` (guarded by `test_standalone.py`);
logger `logging.getLogger("belegtool_compress")`. `formats/compress_pdf_bytes.py` and `services/cpu.py` are thin re-exports (guarded by
`tests/test_compress_reexports.py`; `core.engine` lazy-imports through the shim). `pixels.capped_dpi` is a deliberate small copy of
`services/render.capped_dpi` (render.py stays in the host; keep both budgets in step). Stay in the host: `render.py`, `render_service.py`,
`variant_store`/`variant_blobs`, `infra/limits`, and the engine-bound tests (`test_engine_compress_cancel.py`, `test_engine_jpg_color.py`).
Installed non-editable via `./packages/belegtool-compress` in `requirements.txt`; `belegtool.spec` collects it; CI has an isolated
`belegtool-compress` job plus a non-`-I` import check of the re-exports. Re-run `pip install ./packages/belegtool-compress` after every change
to it. Extraction: `git filter-repo --subdirectory-filter packages/belegtool-compress` (see its `EXTRACTION.md`).

**Non-raster work runs on pikepdf (2026-11-25, step 1 of [`docs/pymupdf-extract-msg-ersatz.md`](docs/pymupdf-extract-msg-ersatz.md)):** `belegtool_compress/pdfinfo.py` (`page_count`, `page_dims` = CropBox∩MediaBox, inherited attrs, /Rotate snapped to 90°, /UserUnit, MuPDF's
Letter default for a missing/empty box; `services/render.page_count/page_dims` delegate), `RealEngine.split_chunks` (pikepdf page copy; **internal
GoTo/Dest links are dropped** per part, URI links stay), the compressor's image→PDF assembly `_assemble_pdf` (JPEG as DCT, 8-bit PNG as its deflated
IDAT + predictor, identical page images shared; PNG variants are now genuinely small instead of raw samples, 16-bit grey PNG no longer renders black)
and the page-count guards. Parity tests (fitz as oracle): `tests/test_pdf_nonraster_parity.py`, `packages/belegtool-compress/tests/test_assemble_*.py`.

**PyMuPDF is gone from the product (2026-11-26, step 3): rasterizing = pypdfium2 behind `belegtool_compress/raster.py`.**
`raster.open_pdf(bytes)` → `page_count` / `page_size(i)` (points as displayed, rotation/CropBox/UserUnit) / `render(i, dpi, gray)` (PIL, white
background, annotations + form fields drawn); `services/render.py` (`render_page`, `render_pdf_to_images/pngs`) and `compress.py`
(`_render_chunk`/`_render_one_page`) call ONLY this interface. Backend = `PdfiumBackend` (pypdfium2 5.15.2, BSD-3/Apache-2.0, bundled `pdfium.dll`);
`BELEG_RASTER` selects another registered backend (default `pdfium`; PyMuPDF is registered only by the test oracle `packages/belegtool-compress/tests/fitz_backend.py`).
Behaviour worth knowing (all measured in [`docs/pdfium-spike.md`](docs/pdfium-spike.md), tool `scripts/raster_compare.py`):
- **pdfium is NOT thread safe → one process-wide `PriorityLock`** around every pdfium call. A *foreground* session (interactive preview page; default for
  a non-pool thread) registers priority for its whole lifetime, so queued *background* work (threads marked by `cpu.set_current_thread_below_normal`
  = the prefetch and compression pools, or `background=True`) never slips in between its open/size/render calls: an interactive page waits for at most one
  running render (≈ 1.7× the single-page time under 4 background threads; a plain `Lock` gave 5×). Consequence: **the pools give fairness, not throughput** (they were GIL-bound
  ~1.2× under PyMuPDF too). Never open a foreground session and then wait for background work on the same thread.
- **/UserUnit is applied by us** (pdfium ignores it); **grey = RGB render + Pillow `L`** (not pdfium's grayscale flag, not MuPDF's brightening `csGRAY`):
  colour stamps in the grey `jpg`/`png` variants are a bit darker than before. Pixel size = `ceil(pt·dpi/72)` like before; pixel budget `MAX_RENDER_PIXELS` unchanged
  (plus a 256 MP hard cap in the backend).
- A document is opened **per session and closed deterministically** (no leak over 1000 pages); a wrong password / garbage raises `RasterError` (→ empty preview / skipped candidate).
- Parity tests with PyMuPDF as optional oracle: `packages/belegtool-compress/tests/test_raster_parity.py` (+ `test_raster_pdfium.py`, no oracle needed); licence guard
  `tests/test_no_agpl_pdf_deps.py`; shipped-set smoke `scripts/smoke_no_pymupdf.py` (CI `no-pymupdf-runtime`); CI `raster-parity` (ubuntu + windows).
  PyMuPDF stays in `requirements-dev.txt` (+ numpy for the tool) as test oracle and fixture generator for `tests/`/`scripts/` only.
  **Windows-only unverified:** PyInstaller bundling of `pypdfium2_raw/pdfium.dll`, rendering under RDP, real scans.

### Data model

| File | Role |
|---|---|
| `formats/pdf_node.py` | `PDFNode`: serialization carrier for the `.belegtool` I/O path only (bytes + metadata, `to_dict`/`from_recursive_array`; `copy` removed 2026-11-04, I-2). **No rendering, no operations** — split/merge/rotate/compress live in `core/engine` |
| `formats/pdf_storage.py` | `PDFStorage`: JSON serialization, export with TOC, .belegtool format |

### Import & Export

| File | Role |
|---|---|
| `universal_importer/` | Multi-format import **package**: `importer.py` (the `UniversalImporter` detect+dispatch class), `converters.py` (per-format functions: images jpg/png/webp/heic, Office via COM, txt/html + the `data:`/`cid:` link guard), `archives.py` (thin shim over the separable package `belegtool_archives`, see below: ZIP/TAR/email extraction + bomb guards, with `UniversalImporter` injected as the member converter). `__init__` re-exports the public surface. |
| `formats/toc_export.py` | PDF export with printed TOC, clickable annotations (pikepdf), sidebar bookmarks, auto-split >100 pages |
| `formats/compress_pdf_bytes.py` | Render-based compression (JPG/PNG), pikepdf structural compression, method comparison |

### Utilities

| File | Role |
|---|---|
| `infra/tools.py` | `sanitize_pdf`: repair broken PDFs (xref/object streams) via pikepdf — a no-op on readable files. Wired into `PDFStorage._load_pdf`'s plain-PDF branch (never the `.belegtool` path). |
| `version_info.py` | `APP_NAME`, `VERSION` (currently 3.11.4) |
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
| `services/cpu.py` | **CPU-fairness primitives** for the background pools: `worker_count` (capped 4 local / 2 RDP, `BELEG_WORKERS` override), `set_current_thread_below_normal` (so background work yields to interactive/other sessions), `SystemCpuSampler` (`GetSystemTimes`, no extra dep → prefetch backs off under load), `is_remote_session`. Pure/injected → unit-tested headless. ⚠ pdfium rasterization is serialized by `raster.PDFIUM_LOCK` (priority lock, see *PyMuPDF is gone*), so the pool's value is fairness + foreground preemption, not throughput (true multicore would need processes — see Open items). |

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
| `webui/src/ContextMenu.jsx`, `lib/core.js` | Right-click ops (incl. Merge→1 PDF / In neuen Ordner / Status incl. "Kein Status" + folder cascade); thin `window.pywebview.api` wrapper. Pure frontend logic lives in `webui/src/lib/` (`core.js`, `selection.js` incl. `mergeableIds`, `treeNav.js`, `status.js`, `messages.js`, `tags.js`, `tree.js`, `datev.js`, `zoomAnchor.js`). |
| `webui/src/Toolbar.jsx` | Icon-only toolbar (open/import/export/new-window/undo/redo + 🏷️/DATEV toggles); labels in `title`/`aria-label`, export count badge. |
| `webui/src/SaveSplitButton.jsx` | Save split-button: main part saves in place (dirty „•"), caret opens „Speichern unter…" via `hooks/useMenu.js`. |
| `webui/src/DatevBar.jsx` | **The v3.10 in-app DATEV UI** — header „DATEV" toggle (`set_datev_mode`), „von DATEV" badge, write-back / „nach DATEV ablegen" actions. |
| `webui/src/Preview.jsx`, `PreviewPane.jsx` | Virtualized windowed preview (IntersectionObserver + aspect placeholders + ±5 prefetch + per-node scroll memory + zoom anchor via `lib/zoomAnchor.js`); `PreviewPane` is its container. |
| `webui/src/StatusBar.jsx` | Bottom status/notice bar (dirty, page position, notices/errors). |
| `webui/src/ExportDialog.jsx`, `SaveDialog.jsx` | Export-options dialog (TOC / tag index / bookmarks / split + „Nach DATEV ablegen"); save/embed-variants prompt. |
| `webui/src/TagEditor.jsx`, `TagViewBar.jsx` | Tag editor (favourites, multi-select union via `TagMany`) + the search/group view bar. |
| `webui/src/hooks/` | UI hooks: `useKeyboard`, `useSelection`, `useOsFileDrop`, `useDialogs`, `useTagView`, `useResizablePane`, `useModal`, `useMenu` (shared roving-focus/dismiss menu). |
| `webui/src/lib/status.js` | **Pure** status-dot aggregation (leaf/folder, red→yellow→green + black) + `hasUndecided` for the front compression dot; `aggregateStatus` computes ALL rows in one bottom-up pass (Tree `useMemo`, I-5). Tested in `status.test.js`. |
| `webui/src/lib/datev.js` | **Pure** DATEV-mode helpers: `isDatevConnected`, `datevVerdictKey` (verdict→localized message), `datevSavedNotice`, `localBaseName`. Shared by `App.jsx` (organizer) + `pdftool/main.js`. |
| `webui/src/lib/datevFiling.js` | **Pure** DATEV filing-dialog logic shared by organizer + PDF-Tool: `filterClients`, `registersFor`, `yearChoices`, `validateFiling`, `buildFileOpts`, `soleClientGuid`. Tested in `datevFiling.test.js`. |
| `webui/src/pdftool/fileDialog.js` | Vanilla-DOM DATEV **filing dialog** of the PDF-Tool surface (the organizer uses the React `DatevFileDialog`); `openFileDialog(…)` resolves to the `datev_file` opts or null on cancel. Tested in `fileDialog.test.js`. |
| `webui/src/HelpModal.jsx`, `help/content.js` | How-to Help modal (separate from the main UI language switcher): 🇩🇪/🇬🇧 flags toggle the two authoritative versions; help text authored best-effort for all UI languages, unknown → EN fallback; GitHub/mailto correction links. |
| `webui/pdf-tool.html`, `webui/src/pdftool/` (`main.js`, `source.js`) | **PDF-Tool surface** (2nd Vite entry, PDF.js): the host routes a `.pdf`/node binding here (`host._entry_for_kind` / `startup_kind`), it fetches the bound bytes over the bridge (`CoreApi.get_pdf_bytes` / `open_node_in_pdftool` / `close_pdftool`) and renders a **selectable text layer + interactive AcroForm**, plus an **„✎ Text" tool** (PDF.js FreeText editor) and **„💾 Speichern"** → `saveDocument()` → `save_node_back(session, b64)` → `SetNodeBytes` (new source on the node, undoable in the organizer). Added text round-trips as editable FreeText on reopen. External link annotations open `target="_blank"` → pywebview routes them to the **system browser**, never the bridged window (H2 fix 2026-11-04; e2e-guarded, fixture `webui/public/spike-link.pdf` from `scripts/make_pdftool_fixtures.py`). `source.js` (`chooseSource` / `base64ToUint8` / `uint8ToBase64`) is the pure, unit-tested logic. Design + roadmap: [`docs/pdf-tool.md`](docs/pdf-tool.md). |
| `requirements-dev.txt` | Test/dev deps on top of `requirements.txt` (pytest) — `build.ps1` recreates `.build_venv` WITHOUT it; reinstall after a release build. |

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
    `vite.config.js` forces `pool: 'vmThreads'` (kept after the 2026-11-03 bump to vitest 4.1.12,
    which reportedly fixes the pools — dropping it is untested) — and **`vi.mock()` does not take effect under
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
| `pypdfium2` 5.15.2 (BSD-3/Apache-2.0, bundles `pdfium.dll`) | PDF **rasterizing** only, via `belegtool_compress/raster.py` (`services/render.py`, `compress.py`); replaced PyMuPDF (AGPL/Artifex) 2026-11-26 — PyMuPDF is dev/test-only now (`requirements-dev.txt`: oracle + fixture generators) |
| `Pillow` | Image processing; HEIC support via `pillow-heif` |
| `pikepdf` | Advanced PDF manipulation (annotations, outline/bookmarks) |
| `pypdf` | PDF read/write (base) |
| `reportlab` | Render TOC pages (Canvas) |
| `xhtml2pdf` | HTML-to-PDF |
| `olefile` 0.47 (BSD-2) + `compressed-rtf` 1.0.7 (MIT) | Own Outlook `.msg` reader in `belegtool_archives/msg_reader.py` (replaced extract-msg GPLv3 + RTFDE LGPL on 2026-11-26) |
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
Split, merge (with DPI conflict check), create folder, delete, rename, drag-and-drop. (A copy command does not exist yet — see Planned changes.)

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
  `open` **restores from `.bak`** if it finds the file truncated (interrupted save). Hardened
  2026-11-04 (QS N-2/Neben-1): an incomplete `WriteFile` raises (no silent short write), a
  sibling **`.wip` marker** brackets the in-place write — `restore_from_bak` treats a leftover
  marker as authoritative (the old head+tail heuristic alone accepted a half-new/half-old file),
  and a retry after a failed save keeps the GOOD `.bak` instead of refreshing it from the
  broken on-disk state. Lock-off saving is **atomic** since 2026-11-04 (temp file +
  `os.replace`; legacy in-place fallback only when the target is held open elsewhere).
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
- **Lazy service** ([`datev/inapp.py`](https://github.com/tobiasheinrichfaska/datev-dokab/blob/main/datev/inapp.py) `DatevService`) — built on first use over
  the reusable, injected-transport [`datev/client.py`](https://github.com/tobiasheinrichfaska/datev-dokab/blob/main/datev/client.py) (SSO curl). Imports the
  `datev` package only when mode is on. `CoreApi._datev_get_service()` is the gate.
- **Provenance** — the DATEV origin `{doc_guid, file_id, structure_item_id,
  correspondence_partner_guid, source_name}` lives on the **root** `Node.datev` field and
  **round-trips in `.belegtool`** (threaded through `model`/`pdf_node`/`bridge`/`pdf_storage`;
  set/cleared by the in-process **`SetDatev`** command, applied silently — origin metadata, no
  undo/dirty). The write-back **baseline** (opened sha256 + `change_date_time` + checked_out)
  is per-session runtime state in `CoreApi._datev_baseline`, **not** persisted.
- **On open** (`CoreApi._datev_capture_on_open`) — a DATEV **checkout path**
  (`…\<doc-guid>\<file-id>`, via `parse_checkout_path`) captures provenance + baseline, shows a
  „from DATEV" badge, and warns up front if the document was already checked out. ⚠️ The content
  baseline hashes the **RAW checkout file on disk** (== the server file), **not** the
  re-serialised effective bytes — `_datev_effective_bytes` runs the doc through `PdfWriter`
  (normalises xref/streams → never byte-identical to the raw file), so hashing *that* made every
  first write-back of an unedited checkout falsely report `conflict_content` (fixed; regression
  `test_open_unedited_checkout_writeback_is_ok_not_false_conflict`).
- **Two surfaces (`unterscheide`) — the host routes by file TYPE.** ⚠️ **DATEV stores, checks out,
  and returns a document as the exact file type it was handed** (confirmed live from use, 2026-07-01):
  a document filed as a **`.belegtool`** is checked out again as a **`.belegtool`** → the
  **organizer** (full tree — the `/JSONStructure` is preserved end-to-end, never flattened); a genuine
  **`.pdf`** document is checked out as a **`.pdf`** → the **PDF-Tool** surface
  ([`webui/src/pdftool/main.js`](webui/pdf-tool.html)). A structure-bearing document therefore never
  returns on the single-PDF surface, so the two never cross (an audit that assumed "a checkout is
  always a `.pdf`" was a false positive on exactly this point). **Both** run through `CoreApi.open`, so provenance
  is captured either way, and **both** offer DATEV write-back: the organizer via `DatevBar`, the
  PDF-Tool via a „🔗 Nach DATEV zurückschreiben" / „📤 Nach DATEV ablegen" toolbar button
  (revealed by the pure `datevAction({datevMode, connected})` only for a `.pdf` in DATEV mode).
  The PDF-Tool bakes its edits before a DATEV op via **`CoreApi.update_pdf_bytes`** — a
  **session-only** write of the first leaf (NO disk write), so a refused/declined write-back
  **never clobbers the on-disk checkout `.pdf`**; the file is written only AFTER a successful
  verdict by `_datev_local_persist`. The plain „💾 Speichern" instead uses `save_pdf_bytes`
  (session + disk) for a bridge `.pdf`, or `save_node_back` for a node binding (`save_node_back`
  rejects a bridge session — no binding — which is why the dedicated bridge path exists).
- **Format-aware local save** (`_datev_local_persist`): the parallel local save writes the
  bound path's **own format** — a `.belegtool` keeps the full structure + provenance (so the
  link round-trips); a checkout **`.pdf`** is overwritten with the **clean effective PDF bytes**
  (never inject the `.belegtool` structure into a DATEV checkout file). The result carries
  `local_kind` ('belegtool' | 'pdf') and the UI shows the **saved file name** in the success
  notice (`datevSavedNotice`) so the user can always tell which format landed on disk. Document
  names that become a real temp/disk path (the `datev_export` part files, the `materialize_subset`
  view title) are run through the shared **`CoreApi._safe_filename`** (strips path separators,
  illegal chars, trailing dots/spaces, and Windows reserved device names like `NUL`/`COM1`).
- **On save** — the guarded write-back: `HostApi.save_to_datev` asks „nach DATEV zurückschreiben?",
  then `CoreApi.datev_save_back` re-reads the server NOW and runs the **pure**
  [`datev/writeback.py`](https://github.com/tobiasheinrichfaska/datev-dokab/blob/main/datev/writeback.py) `decide_save_back` (not checked out · `change_date_time`
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
- The standalone probe (`tools/datev_probe/probe_gui.py` + entry `datev_probe.py` → `DATEV-Probe.exe`) is **maintained research
  tooling**, not shipped in the BelegTool release. It is the live-DATEVconnect investigation
  vehicle and is used for manual housekeeping (e.g. `delete_document` of test docs). It is the
  **sole** caller of the `datev/client.py` read surface (`list_domains`/`list_documents`/
  `get_document_raw`/`list_document_states`/`delete_document`), the `provenance.py` scorers
  (`provenance_stats`/`match_entries`), and the file-config/urllib-transport path
  (`config.load_config`/`resolve_auth_mode`, `transport.make_urllib_transport`). **These are NOT
  dead code** — they are the probe's API; an audit that treats "probe = unshipped" will keep
  flagging them. Keep them while the probe is maintained; only remove them if the probe is retired.
- `DatevService.status()` returns `feature` + `keeps_revisions` (DokAb keeps no revision). The
  in-app flow targets **DokAb only**, so the hard-coded "no revision — overwrite" warning in
  `HostApi.save_to_datev`'s confirm dialog is always correct; `keeps_revisions` is a deliberate
  backend status field (a future DMS/DokAbRev-aware conditional warning would consume it), not an
  unused value to strip.

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
[`manual_tests/`](manual_tests/README.md) — **German since 2026-10-10** (workspace rule:
product text incl. `manual_tests` is German). 11 areas (`00_installation` … `10_datev`),
85 test cases. Keep them current when user-facing flows change (workspace convention).

**Tester kit (generated).** The Markdown files are the single source; from them
`scripts/build_testkit.py` builds [`manual_tests/testpakete/`](manual_tests/testpakete/):
one folder per test case with the instruction **PDF** and a `Beispieldateien/` folder
holding exactly the sample files that case needs, plus `00_Start_hier.pdf` (overview +
index) and the Store installation guide
([`docs/installation-microsoft-store.md`](docs/installation-microsoft-store.md) →
`docs/Installation_Microsoft_Store.pdf`, copied into the kit).

```powershell
.build_venv\Scripts\python.exe scripts\build_testkit.py            # samples + all PDFs
.build_venv\Scripts\python.exe scripts\build_testkit.py --check    # validate sources only
```

| File | Role |
|---|---|
| `scripts/build_testkit.py` | CLI + orchestration; owns `manual_tests/testpakete/` (prunes what it did not write); writes `manual_tests/testpakete.manifest.json` (sha256 of the HTML each PDF was printed from) |
| `scripts/testkit/cases.py` | **Pure** model: parse `NN_<area>.md` → `Area`/`Case`/`Section`, `validate`, `slugify`. Case format documented in `manual_tests/README.md` |
| `scripts/testkit/markdown.py` | **Pure** Markdown-subset → HTML (no Markdown lib in the build venv) |
| `scripts/testkit/page.py` | HTML/CSS page templates (presentation only) |
| `scripts/testkit/pdf.py` | Headless **Edge** print (`--print-to-pdf`, own profile dir) + metadata normalisation → byte-reproducible PDFs |
| `scripts/testkit/samples.py` | Sample catalog (name → description + builder): text PDFs, colour "scans", images, mails, archives, `.belegtool` trees declared as data. All synthetic, all reproducible |
| `tests/test_testkit.py` | Parser/renderer tests, the real sources, and each sample run through the app's own code (compressible vs. no-gain, refusals, nesting limit) |

- **Definition of done:** edit a test → rerun the build in the same session.
  `test_kit_on_disk_matches_the_sources` fails on a stale kit (it recomputes the manifest —
  no browser needed). A **version bump changes every PDF** (the footer states the version),
  so regenerate on release.
- PDFs are printed through Edge on purpose: the app's toolbar is emoji rendered by
  WebView2, so the instructions show the identical glyphs. Needs Microsoft Edge.
- Kit PDFs/JPG/PNG/HEIC go to **Git LFS** (existing `.gitattributes` rules); the synthetic
  sample `.belegtool` files are exempted from the `*.belegtool` ignore rule. ⚠ GitHub's
  "Download ZIP" contains LFS **pointers**, not the PDFs — hand testers a zip of the folder
  (or attach it to a Release).
- **Test ids are unique only within an area** (MT-50 exists in 07, 08 and 09 — historical).
  PDF names carry the area number; renumbering is open (it would invalidate ids already
  cited in issues).

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

Current version: **v3.11.4** — audit-fix release on top of v3.11.3 (2026-11-04, 31-finding
audit + adversarial agent review): (1) *Compression can no longer silently lose pages* — a
candidate whose page count differs from the source is dropped (the old guard lived in dead
code; a truncated variant shifted every FOLLOWING node's pages on reload). (2) *A link in an
untrusted PDF opens the system browser*, never the bridged app window (pywebview re-injects
the JS API into whatever loads there; e2e-guarded, new MT-54). (3) *Archive-import hardening*:
bzip2/LZMA zip members refused (CPython inflates them unbounded), tar streams (gz/bz2/xz,
multi-stream) inflated bounded by the remaining budget and charged, double-compression blocked
(plain-tar parse), oversized reads charged, exhausted budget degrades members visibly instead
of aborting, total folder depth capped at 120 (< loader limit 200), per-member failures show
their reason. (4) *Forwarded `.msg` keeps its attachments* (CFB-signature routing; the strict
xfail turned red as designed). (5) OOXML `.rels` scan now a real XML parse (single quotes /
char-refs / prefixed elements no longer bypass it; attributes read by their EXACT unqualified
OPC name, a namespaced/case-variant duplicate like `x:TargetMode` fails closed — QS counter-
review 2026-11-04); `curl.exe`/`whoami` called by absolute
System32 path; malformed wire commands return `{ok:false}`; close-guard keeps a dirty window
open when the confirm dialog breaks; engine variant layer freed on close; prefetch/close race
on `_pcount` fixed. (6) Docs: DATA_CONTRACT `uid` corrected, data-model Werkseinstellungen,
deep-copy claims removed, `requirements-dev.txt` (pytest), `testpaths = tests`, vitest
`testTimeout`. Deferred: shared rasterization (L2), Split→fitz (L5), FreeText/JBIG2 e2e,
import-router + CoreApi split (architecture). Drop-Handler: erledigt 2026-11-25; host-seitiger
WebView2-`AllowExternalDrop=false` bleibt offen (nur unter Windows prüfbar).

**v3.11.4 — second QS round (2026-11-04, Fable review of the UNCHANGED core + Opus
verification of every finding, all fixed test-first):** (H-1) *a corrupt `.belegtool` can no
longer destroy itself* — load degradations (unreadable page tree after a `sanitize_pdf` repair
attempt, structure fallback, skipped/truncated nodes, hostile `pdf_length`) are collected in
`PDFStorage.load_warnings`, surfaced by `CoreApi.open` as `warning`, and a degraded open does
NOT bind the path (Ctrl+S → Save-As; import of a degraded file is refused with the reason);
(M-1) *unlocked save is atomic* (temp + `os.replace`, in-place fallback when the target is held
open); (M-2) *Split/Merge carry tags + Veranlagungszeitraum + dpi_original* (folder variant:
tags on the folder; merge: union/span); (N-1) *split-export TOC* — "In anderen Dateien:" header
also before leading cross-refs, cross-ref page numbers use the TARGET part's TOC offset (two-pass
render); (N-2/Neben-1) *file lock* — a short `WriteFile` is an error, a `.wip` in-flight marker
makes `restore_from_bak` reliable (head+tail heuristic alone accepted hybrid files) and a retry
never overwrites the good `.bak`; (N-3) *failed export page-slices* carry their REAL page count
and reach the user via `warning`; (N-5) *preview render/geometry failures show an error banner*
instead of vanishing in empty catches; (I-1) `insert_child`/`move_node` raise `KeyError` on a
missing target (never silently lose a node); (I-2) dead `export_selection`/`PDFNode.copy`
removed; (I-3) `SetNodeBytes` recomputes `pdf_length`; (I-4) prefetch docstring corrected;
(I-5) tree status dots via ONE bottom-up `aggregateStatus` pass (`useMemo` on the tree) instead
of a `leaves()` walk per folder row; (I-6) undo back to the saved state clears dirty (identity
marker in `DocumentSession`, `dirty` in `_doc_response_locked`, UI mirrors it). 12 new i18n keys
(de+en, PENDING batch), new manual tests MT-15d (corrupt file) + notes in MT-06/07/14/15.

**v3.11.4 — Auflagen aus der Opus-Bewertung der Fixes (2026-11-04, alle umgesetzt):**
(H-1a) the repair attempt is REAL now — a full pikepdf rewrite (sanitize_pdf returned unchanged
bytes whenever PdfReader constructed), also triggered when pypdf tolerantly reports 0 pages
although the structure has leaves; a successful repair stays degraded ("Seitenbaum repariert –
bitte als neue Datei speichern"); (H-1b) a `.belegtool` whose `/JSONStructure` marker moved into
a compressed object stream (qpdf/Acrobat rewrite) now loads its structure — the app's own
extension always does the full metadata read, and a `.belegtool` WITHOUT a structure degrades
loudly ("Dokumentstruktur fehlt"); (H-1c) pages beyond what the structure describes warn
("… Seiten mehr als die Struktur beschreibt") instead of being dropped on the next save;
(H-1d) Save-As of a degraded session suggests `<name> (wiederhergestellt)`
(`CoreApi.session_degraded`, cleared on save/healthy reopen/close) so Enter+Ersetzen cannot hit
the corrupt original; (N-2) `write_through_lock` removes `.bak` BEFORE `.wip` and both guarded
(a raced `restore_from_bak` no longer fails a COMPLETED save), plus a test exercising the REAL
`FileLock.overwrite` short-write path; (M-2-Rest) `vz_start`/`vz_end` coerce to int-or-None on
load (mixed types crashed Merge's min/max span); the N-1 test now uses 43 docs/15 per part so
the parts' TOC page counts really differ (the 45-doc variant was offset-blind); MT-15d ships a
prepared `Defekte_Mappe.belegtool` sample (hand-made random corruption triggered the warning in
only 5 of 30 tries) with a kit test asserting it reliably degrades.

**v3.11.4 — Delta-Review-Runde (2026-11-04, Fable-Review der beiden zuvor ungeprüften
Fix-Deltas, alle Auflagen umgesetzt):** the `.rels` scan closes three further fail-open gaps —
(A-1) duplicate ZIP entry names refuse (`zipfile` reads the LAST entry, Word's OPC reader may
read another; no legitimate tool produces duplicates), (A-2) a `TargetMode` VALUE that is not
exactly `Internal`/`External` refuses (whitespace variants were treated as internal), (A-3) a
case-variant `<relationship>` element refuses like attribute look-alikes. Load integrity: (B-1)
float vz values coerce consistently (2024.0 → 2024, 2024.5 drops like the string), (B-4) a
folder-only `.belegtool` with an unreadable wrapper warns + stays unbound (the failed-repair
branch had reassigned `reader`, slipping it through), (B-3) dead `data = repaired` assignment
removed. B-2 (locked-save micro-window) + A-4 (absolute URL without TargetMode) documented as
accepted residuals.

v3.11.3 — security + nesting release on top of v3.11.2 (2026-11-03):
(1) *Dependency security updates* closing every open Dependabot alert — shipped: **Pillow 13.0.0**
(was 12.2.0, incl. 5 critical), **pypdf 6.21.4**, **pdfjs-dist 6.5.438** (a malicious PDF could run
JavaScript in the PDF-Tool); dev toolchain: vite 8.3.5, vitest 4.1.12, undici 7.30.1, minimatch 11
(override) and refreshed transitive deps (`npm audit`: 0). (2) *Nested containers open up to
**10** levels* (was 3) — the shared byte/member budget still bounds the total work. (3) *The
webui build fails loudly* when a PDF.js asset folder (`cmaps`/`standard_fonts`/`wasm`/`iccs`) is
missing instead of silently shipping blank scan pages. (4) Tester kit + German manual tests, the
synthetic `.msg` fixture, `import/` emptied into `import-archiv/`, DATEV specs moved to `vendor/`.

v3.11.2 built on **v3.11.1** — terminal-server / DATEV-checkout hardening on top of v3.11.0:
**scanned PDFs render** in the PDF-Tool (bundled PDF.js JBIG2/JPEG2000 wasm + cmaps), the DATEV
checkout write-back is **fixed end-to-end** (server returns `structure_item_id` as a numeric string;
the checkout-path number can be a DokOrg working-copy id, so the real `document_file_id` +
`structure_item_id` are resolved from the server via the doc GUID), **checkout ownership** is matched
by the Windows session user (the machine label / Nutzer-GUID / SID are unreliable on the TS — DATEV
ticket), and a **checked-out document is saved the native way** (💾 Speichern → local working copy →
check in via DATEV; the „🔗 Nach DATEV zurückschreiben" button is hidden while checked out). The DATEV
write-back is now **structure-preserving** — a `.belegtool` is uploaded as its own bytes (pages **+**
embedded `/JSONStructure`), so DATEV shows a normal PDF *and* the tree round-trips on re-open instead
of being flattened (a checkout `.pdf` still uploads its plain PDF). Startup is instrumented
(`belegtool_startup.log`) and the install-to-local-disk rule is documented. A lean always-on
`belegtool_diag.log` trail remains for field diagnosis.

**v3.11.2 changelog:** (1) *DATEV type-preservation clarified.* DATEV
stores/checks out a document **as the file type it was given**, so a `.belegtool` filed to DATEV is
checked out again as a `.belegtool` (→ organizer, `/JSONStructure` preserved end-to-end) and only a
genuine `.pdf` rides the PDF-Tool — the two never cross. An audit that assumed "a checkout is always a
`.pdf`" (and inferred a structure-flattening / leaf-0 data-loss bug) was a **false positive** and is
retracted. (2) *Stale DATEV connect-worker race fixed* via a `_datev_connect_epoch` token: a connect
worker from a superseded epoch (an off→on toggle mid-connect) now discards its result instead of
adopting a stale service (regression test in `test_datev_coreapi.py`). (3) *Checkout-ownership
diagnostic enriched* — the `[datev] checkout ownership:` breadcrumb now logs both sides (checkout
computer / session-user / user id+is_deleted vs. this session's computername / username / SID /
connection-user + `same_session_user`/`same_dms_user`/`sid_match`), so the match can be hardened to a
computer+owner match once a field rerun confirms the deleted-Nutzer is resolved.

v3.11.0 extended the v3.10.0 beta (icon-only toolbar, Save split-button, multi-select tagging,
„Neuer Ordner" at selection, zoom-keeps-position, nested archive/mail + subfolders, configurable
export split, PDF-Tool text editor, in-app DATEV integration) with the **DATEV filing dialog**
(searchable Mandant + folder/register + Belegdatum + Veranlagungsjahr/-monat), a **non-blocking
background DATEV connect**, `datev.config.json` host config, and the **no-connection /
no-client-list ⇒ no DATEV write** guard.

---

## Known Limitations

Current accepted shortcomings and non-obvious behaviours (lift into release notes as needed).
Deferred *features* and the full rationale live under **Open / deferred items** below.

- **Windows-only.** PyInstaller `win64`, Edge WebView2 GUI, hard `pywin32`/`pythonnet` deps,
  COM-based Office import. The PDF core is cross-platform but no port is maintained
  (community RFC: [`docs/cross-platform-port.md`](docs/cross-platform-port.md)).
- **Install to LOCAL disk — never a roaming/redirected profile (terminal-server startup).**
  *(Diagnosed 2026-06-29.)* The onedir bootloader loads hundreds of `_internal/` DLLs **before**
  any app code runs. Launched from a **network-backed/redirected user-profile path** (e.g.
  `C:\Users\<user>\Downloads`) on a terminal server, that load is over the network → **~13 s**
  startup vs **~3 s** on local disk. **Not** Mark-of-the-Web (unblock didn't change it) and **not**
  Defender (an exclusion didn't change it). Fix: install to a **local machine path**
  (`C:\Program Files\BelegTool` / `C:\BelegTool`). Startup is instrumented — `belegtool_startup.log`
  next to the exe times each phase (process→main is the bootloader; main→first-paint is our code),
  and on RDP WebView2 is forced to software rendering. The connect is non-blocking, so DATEV mode
  never delays startup.
- **A checked-out DATEV document is NEVER written back via the API — save the local working copy +
  check in via DATEV (mechanism A).** *(Confirmed live 2026-06-30.)* The DATEVconnect server refuses
  `update_structure_item` on a checked-out document with **"The document can't be changed because it
  is checked out"**. So BelegTool does not API-write-back a checkout: the PDF-Tool **hides the
  „🔗 Nach DATEV zurückschreiben" button when the doc is checked out** ([source.js](webui/src/pdftool/source.js)
  `datevAction` returns `null`), and **💾 Speichern** writes the local working copy (the user checks
  it in via DATEV). The backend keeps a safety net: if the write-back is invoked anyway (e.g. the
  non-blocking connect wasn't ready at open, so the button showed), `writeback()` returns verdict
  `checked_out_self` and `datev_save_back` saves the local working copy instead of pushing to DATEV.
  The in-place API write-back still applies to a connected doc that is **not** checked out.
- **DATEV checkout ownership is matched by the Windows *session user*, not the Nutzer GUID — DATEV
  data problem (internal DATEV support-ticket note, kept locally).**
  *(Diagnosed 2026-06-29/30 on the live terminal server.)* Deciding whether a checkout is **yours**
  (to allow it / to know it's not someone else's) can't rely on either signal we'd expect: (1)
  `checkout_computer` is `"WTS (USER1)"` — `WTS` is a DATEV/terminal-server **session label**, not the
  Windows `COMPUTERNAME` (`TSHOST`), so the machine string never matches; (2) the checkout was
  stamped by a **now-deleted Nutzer** (`id 11111111…, is_deleted=true`) whose GUID differs from the
  live connection's (`22222222…`), and **zero IAM records are linked to the running Windows SID**
  (`records_sharing_my_sid=0`, `checkout_user_sid=None`) — so neither the Nutzer-GUID nor the SID can
  map "current Windows user ↔ Nutzer". **Accepted behaviour:** ownership is decided by the **Windows
  session user** in the label (`USER1 == user1`), which uniquely identifies the person on the
  single-TS setup; the DMS-id remains an *additional* accept signal. **The root cause — a deleted
  Nutzer holding a live checkout / no SID linkage — is a DATEV-side issue (support ticket drafted).**
  Evidence: `belegtool_diag.log` `[datev] checkout ownership:` lines. Consequence: two *different* Windows
  users with checkouts are still correctly distinguished; the machine label is intentionally ignored.
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
  Accepted bounds: recursion stops at **`_ARCHIVE_MAX_DEPTH = 10`** (raised from 3 in v3.11.3; a
  deeper container shows „… zu tief verschachtelt"); the bomb budget is **shared across levels**.
  Hardened 2026-11-04 (v3.11.4): an oversized read is **charged** to the budget before it fails
  (nested retries can't redo budget-sized work for free) and once the budget is spent every
  following member degrades visibly as „… – nicht importierbar (Limit überschritten)" — one bad
  inner container never aborts the import. Zip members are limited to **stored/deflate**
  (bzip2/LZMA inflate unbounded inside CPython's zipfile → refused with their reason); a
  gz/bz2/xz tar STREAM is inflated bounded by the REMAINING budget and charged, multi-stream
  (pigz/pbzip2) included, and the result is parsed as PLAIN tar only (no auto-detect →
  double-compression can't reopen the unbounded path). The TOTAL folder depth one import can
  build is capped at **`_MAX_TOTAL_FOLDER_DEPTH = 120`** (nesting × member-path folders
  combined; overflow folds into names) so a crafted archive can never produce a tree the
  `.belegtool` loader (`_MAX_TREE_DEPTH = 200`) refuses to REOPEN — all guarded by
  `packages/belegtool-archives/tests/test_zip_member_guard.py` + `packages/belegtool-archives/tests/test_archive_total_depth.py`.
- **Depth cap is per IMPORT, not per TREE** *(QS-Gegenprüfung 2026-11-04, N-1 — accepted)*: there is
  no depth check at the insertion target or on save, so importing a ~120-deep archive INTO the
  deepest folder of a previously imported ~120-deep archive can build >200 levels — save succeeds,
  reopen is refused by the loader. Needs stacked crafted archives plus a deliberate user action;
  follow-up idea: save-side depth warning or insert clamping.
- **Accepted residuals from the 2026-11-04 QS assessment round** (documented, not fixed):
  (1) whole (unsliced) leaves whose bytes fail in `_export_nodes_to_bytes` still only log —
  TOC offsets then shift within that export; made unlikely by the H-1/N-4/I-3 load guards.
  (2) Preview: after a geometry failure a same-id tree change clears the error banner and shows
  „Keine Vorschau" until the node is re-selected (the failed `{count: 0}` sits in `geomCache`).
  (3) `mark_saved` races a concurrent same-session edit between serialize and flag (pre-existing;
  unreachable via the modal single-window UI). (4) M-1 hints: an `fsync` error on exotic SMB/NAS
  shares now fails a save that silently "succeeded" before (intended — the bytes were not durable);
  a crash can leave a `.tmp-<pid>` sibling (harmless, overwritten/removed next save). (5) With the
  env-gated file lock ON, a SECOND user's `acquire_lock` runs `restore_from_bak` BEFORE its lock
  attempt — a concurrent restore during an in-flight save is mitigated (guarded removes), but
  reordering restore-after-lock is a deferred follow-up. (6) The open-warning banner shows the
  full joined warning list (very many damaged nodes → long message). (7) Locked save: between a
  completed `overwrite` and the `.bak`/`.wip` removal there is a micro-window in which a crash
  rolls the (never acknowledged) save back to the previous state on next open — real loss only
  if BOTH removes fail with the save already reported ok (exotic, e.g. AV holding both files).
  (8) A Relationship with an absolute URL but NO TargetMode is accepted (OPC default Internal;
  conformant parsers reject absolute internal URIs — relies on Word being conformant).
- **Two narrow close-time races, no data loss** *(QS-Gegenprüfung 2026-11-04, N-2/N-3 — accepted)*:
  (1) `_count_for` without a `session` arg (`_seed_single`, `page_count`) can re-insert a
  `(node_id, version)→int` page count into `_pcount` after a parallel `close_session` (tiny, no
  byte payload; the long prefetch path IS guarded). (2) `open()` seeds variants before the session
  is registered, so a close of the SAME source in another window during that window can prune the
  fresh seeds (`prune_persisted` sees them as orphaned) — cost is a recompute, never corruption.
- **No direct Outlook drag-and-drop** — Outlook hands items over as OLE virtual files; import a
  `.msg`/`.eml` instead. No automatic DATEV check-in on document close (manual re-import in DATEV).
- **Multicore rasterization is GIL-limited (~1.2× on 4 threads)** — thread parallelism buys
  fairness/preemption, not throughput; true multicore would need a process pool (deferred).
- **Variants grow the file** — computed compression variants are embedded in the `.belegtool`
  (no sidecar). Split parts in **already-saved** files keep the old `no_compression` flag until
  re-split.
- **DATEV mode (v3.10.0, extended v3.11.0) — accepted bounds.** Off by default; **write-back only
  succeeds when the document was opened from a DATEV checkout path and still byte-matches the server
  file** — a reopened `.belegtool` (or any structural transform) safely reports `conflict_content`
  and falls back to a local save (never a blind overwrite). DokAb keeps **no revision**, so the write
  is a permanent overwrite (guarded; a local backup is written first). **v3.11.0 — file-to-DATEV now
  uses a filing dialog** (a required **Bezeichnung** = the DATEV document **name**, prefilled from the
  document name; searchable Mandant dropdown + folder/register pickers + Belegdatum +
  Veranlagungsjahr/-monat → DocumentCreate `description`/`receipt_date`/`year`/`month`) in BOTH the
  organizer and the PDF-Tool; **filing is refused without a Bezeichnung** (so a filed document is never
  nameless — the "pdf lacks Name" fix) and **without a client list** (master-data unreachable → no safe
  target). The **PDF-Tool offers DATEV for BOTH a directly-opened `.pdf` (bridge) and a node opened
  "in PDF-Tool" (session binding)** — a node binding is never "connected" (the organizer owns any DATEV
  link), so it always offers **file-anew**: filing it creates a new DATEV document AND pushes the baked
  bytes back to the **owner node** (`local_kind: "node"`) so the organizer reflects the edit.
  The connect runs on a **background thread** (the SSO handshake is slow), so the UI never freezes and
  reports `connecting` while it settles; **DATEV writes are refused without a live connection**;
  `datev.config.json` next to the exe drives the host (default **`your-datev-server:58452`** placeholder,
  self-signed trusted). ⚠️ **Opening a DATEV checkout `.pdf` is NON-BLOCKING** (api `_datev_capture_on_open`): it
  no longer waits on the SSO handshake (the v3.10.0 "checkout open takes 12-20 s" freeze). When the
  service is already up it does the full capture as before; while it is still connecting it captures
  only the cheap content baseline (`opened_sha256` from the local file) + marks the server half
  `pending_server`, and `datev_save_back` completes it (`_datev_complete_baseline`) when it runs.
  Trade-off: the up-front "already checked out by someone else" hint then surfaces as a `LOCKED`
  verdict at write-back instead of on open — still safe, just later. The DATEV DocumentCreate fields
  `year`/`month`/`receipt_date` are mapped per the DMS spec but **not yet round-trip-verified on the
  live box** (do this before relying on Veranlagung filing). Live behaviour is verified only by the
  human `manual_tests/10_datev.md` (no DATEVconnect in CI). A failed connect does **not auto-retry**
  (no SSO storm) — toggle DATEV off/on or trigger a write to retry. The DATEVconnect OpenAPI specs in
  `vendor/` are **vendor IP — gitignored, never committed**. `import/` is an inbox: empty after
  processing, processed files go to the gitignored `import-archiv/<timestamp>/`.

- **Security review 2026-11-25 – fixed (4 High):**
  (H-1) HTML/e-mail import: `block_remote_link` returned `None`, xhtml2pdf then falls back to the original
  URI → remote fetch + embedding of local images; now an inert `data:` placeholder, guard
  `tests/test_html_import_e2e.py` (local HTTP server).
  (H-2) `datev/config.py`: `datev.config.json` is never read from the CWD again (only next to the exe /
  source root), `base_url` https-only without userinfo, curl with `--proto =https --proto-redir =https`;
  tests `tests/test_datev_config_security.py`.
  (H-3) Bridge: `HostApi.open` accepts only the host-assigned `startup_path`; `webui/src/lib/dropGuard.js`
  blocks navigation by drop/link in organizer and PDF-Tool; `?file=` only in the dev build.
  (H-4) `UniversalImporter._EXPECTED_MAGIC` pins .docx/.xlsx/.pptx/.odt/.ods/.odp to ZIP magic and
  .doc/.xls/.ppt to OLE magic (RTF/MHT named „.docx" bypassed the `.rels` scan); `tests/test_import_security.py`.
  CSP: erledigt (`vite.config.js` Plugin `csp-meta`, nur Production-Build, `<meta http-equiv>` in `index.html` + `pdf-tool.html`: default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' blob: data:; object-src/base-uri/form-action none). Guard: `webui/e2e/csp.spec.js` via `npm run test:csp` (vite preview, Port 5179; in `test:all`). Nicht verifiziert: WebView2 unter Windows.
  Offen aus dem Review (Medium/Low, nicht behoben): PIL ohne `formats=`-Allowlist, `.belegtool`-Seitenvervielfachung/Knotenlimit, DATEV-Backup nicht zwingend vor Write-back, mkstemp-Handles in `datev/transport.py`, Named-Pipe ohne FIRST_PIPE_INSTANCE, COM-Härtung (DisplayAlerts/TOCTOU/DDE).

- **Licence hygiene (2026-11-26):** `scripts/gen_third_party_notices.py` (stdlib only, offline, reproducible) collects name/version/licence/licence files of every `requirements.txt` distribution + recursive installed deps (pdfium/Skia `BUILD_LICENSES` from the pypdfium2 wheel) + npm runtime packages into `licenses/<dist>/` (**generated, git-ignored, bundled by `belegtool.spec`**, copied next to the exe by `build_msix.ps1`, run by `build.ps1` before PyInstaller) and refreshes the generated table in `THIRD_PARTY_NOTICES.md`; a distribution without licence text is an ERROR (exception list with reason: only `proxy_tools`). `tests/test_third_party_notices.py` (distributions missing in the test venv are SKIPPED with a message, not green). svglib/bidi are collected as `.py` via `module_collection_mode` (LGPL exchangeability, `docs/licence-audit.md` 5a; Windows unverified). SPDX headers (`# SPDX-License-Identifier: AGPL-3.0-or-later` + copyright line from `/LICENSE`) in all `packages/*/**/*.py` AND the main repo's Python sources (`core/ services/ formats/ infra/ universal_importer/ tools/ scripts/ tests/ host.py version_info.py datev_probe.py`, released by the owner and done 2026-11-26): `python scripts/add_spdx_headers.py [--check]`, guard `tests/test_spdx_headers.py` (also checks that every git-tracked `.py` is inside that scope). JS/JSX in `webui/src/` has **no** SPDX headers yet (separate script needed). Each package has its own `CONTRIBUTING.md` with the CLA copied **verbatim** from the main one (`tests/test_package_cla.py` compares; change all four together). Help modal has „Lizenz & Quelltext“ (AGPL §13 source offer); DATEV non-affiliation sentence in README, store listing and help.

- **Open findings from 2026-10-10 (tester-kit build ran every sample through `CoreApi`; none
  fixed yet — triage pending):**
  - **Single-file `.pdf` import bypasses the content gate.** `CoreApi._import_path` hands
    `*.pdf` straight to `PDFStorage`, never to `UniversalImporter.convert`, so
    `verify_content_matches_extension` does not run. A disguised EXE (`MZ…` named `.pdf`), an
    empty file or plain text is imported as a **0-page node, `ok: true`, no message** —
    contradicting the "gate runs on both branches" claim under *Import hardening* and
    `manual_tests` MT-05 step 1 (the archive/e-mail member path refuses correctly). Not code
    execution (bytes are never run). The existing path tests call `convert()` directly, i.e.
    not the route the app takes. Guard: `test_app_import_refuses_exe_masquerading_as_pdf`
    (**strict xfail** — goes red when fixed). Fix needs a decision: a strict `%PDF` prefix
    check would also reject PDFs with leading junk that `sanitize_pdf` repairs today; and
    importing `universal_importer` on the PDF path costs its ~2.6 s cold import.
  - **Password-protected PDF imports silently** (page count readable, `ok: true`) but cannot
    be rendered — the "Datei ist passwortgeschützt" branch of `_friendly_import_error` is
    unreachable on this path.
  - **Multi-page TIFF: only the first page is imported**, silently (`standard_image`).
  - **`.rtf` is imported as plain text** — the PDF shows raw RTF control words.
  - **📂 Öffnen on a plain `.pdf` binds the session to that path**, so 💾 Speichern writes the
    BelegTool-structured PDF **over the original file** without asking. Possibly intended
    (PDF-editor semantics) — confirm; `manual_tests` MT-15c warns the tester.
  - **Store version lags the repo.** The listing is live (Store ID `9PL4D25N00XD`, last
    updated 2026-06-25 ⇒ the 3.9.5 package); no MSIX of 3.10–3.11.3 was submitted. A **3.11.4
    MSIX** was built 2026-11-04 (`packaging/out/BelegTool-3.11.4.0-x64.msix`, package-hygiene
    scan clean) and supersedes the unsubmitted 3.11.3 one (Tobias submits in Partner Center;
    update this entry once certified). Test cases that need newer features carry `**Ab Version:**`.
  - Compression/DPI defects: see *Planned changes — requested 2026-10-10* item 3.

- **Findings from 2026-10-18 — Outlook `.msg` import** (found while adding `.msg` support to the
  sibling box tool):
  - **A forwarded `.msg` loses all its attachments, silently. — FIXED 2026-11-04** (audit fix
    round): routing now checks the OLE/CFB signature (`D0 CF 11 E0 A1 B1 1A E1`) FIRST, so a
    `.msg` whose raw bytes contain `b"From:"`/`b"Content-Type:"` (attached mail, HTML body of an
    English reply) no longer lands in the EML parser. The former strict-xfail guard
    [`packages/belegtool-archives/tests/test_msg_import.py`](https://github.com/tobiasheinrichfaska/belegtool-archives/blob/main/tests/test_msg_import.py) `test_a_forwarded_msg_keeps_its_attachments`
    went red on the fix and is now a normal passing test (marker dropped).
  - **Synthetic `.msg` files for tests:** [`packages/belegtool-archives/tests/msg_fixture.py`](https://github.com/tobiasheinrichfaska/belegtool-archives/blob/main/tests/msg_fixture.py) writes real
    CFB/MSG files (stdlib only: subject, plain/HTML/compressed-RTF body, Unicode or ANSI strings + code page, attachments with long/8.3 names,
    content id, embedded messages, sent date) — so `.msg` paths are tested without real mail (Outlook is never touched).
  - **Licence — RESOLVED 2026-11-26:** `extract-msg` (GPLv3) and its dependency RTFDE (LGPLv3) are **gone** from `requirements.txt`, the
    package metadata, the code and the bundle (`belegtool.spec` excludes them; guard `tests/test_no_gpl_msg_deps.py`: requirements, pyproject,
    AST import scan, spec). Replacement: the own reader `belegtool_archives/msg_reader.py` on **olefile 0.47 (BSD-2-Clause)** and
    **compressed-rtf 1.0.7 (MIT)** (licences verified on PyPI + in the wheels 2026-11-26; `docs/licence-audit.md`). Done test-first: the parity suite
    `tests/test_msg_parity.py` (42 cases) was written and green against extract-msg 0.58.3 on the synthetic files, then the reader replaced it
    with the suite unchanged. **Deliberate deviations** (`test_msg_reader.py`): an embedded `.msg` attachment is recursed into a folder (extract-msg
    degraded it to „nicht importierbar"); an attachment without data / a by-reference attachment is marked and no longer fails the whole mail;
    unreadable strings/RTF degrade instead of raising; the other string type (…001E/…001F) is a fallback; HTML unwrapped from `\fromhtml1` RTF
    is a SIMPLIFIED de-encapsulation (`rtf_deencap.py`, no RTFDE) — equal on the simple synthetic cases, untested on real RTF-wrapped HTML.
    ⚠ **Not verified against real Outlook mails** (none available): Windows test run Phase 4 has the checklist (`docs/windows-pc-testlauf.md`).
  - **History (2026-10-18):** `extract-msg` pulled 16 packages and was GPLv3 — the commercial licence could not cover a build containing it; the
    options researched then (`olefile` own reader, `msg-parser` (2019), `convert-outlook-msg-file`, `msgconvert`) led to the olefile reader above.

> *Fixed 2026-06-29 (PDF-Tool renders scanned PDFs — was BLANK):* PDF.js **v6** keeps its image
> decoders + font/cmap data out of the main bundle — JBIG2 / JPEG2000 (the encodings DATEV scans use)
> decode via `wasm/jbig2.wasm` + `wasm/openjpeg.wasm`, and missing/CJK fonts need `cmaps` +
> `standard_fonts`. `pdftool/main.js` previously set only `workerSrc`, so a scanned PDF **parsed (page
> count correct) but every page rendered blank** (vector/text PDFs were fine — hence the e2e spike-form
> test passed and missed it). Fix: a Vite plugin ([`vite.config.js`](webui/vite.config.js) `pdfjsAssets`)
> copies `cmaps`/`standard_fonts`/`wasm`/`iccs` into `dist/pdfjs/` (and dev-serves them from
> node_modules), and `getDocument` is given `cMapUrl`/`cMapPacked`/`standardFontDataUrl`/`wasmUrl`/`iccUrl`
> (absolute, via `baseURI`, so the worker resolves them). Verified the wasm lands in the PyInstaller
> bundle (`_internal/webui/dist/pdfjs/wasm/`). ⚠️ **Live-verify with a real scanned DATEV checkout** —
> the e2e only covers a vector form.
>
> *Fixed 2026-06-29 (DATEV filing dialog):* (1) a **sole matching client now auto-selects** so „Ablegen"
> enables without a click — a one-option `<select size>` listbox doesn't fire `change` on click in
> WebView2 (pure `soleClientGuid`; the React dialog *derives* the effective selection rather than
> setState-in-effect, and also drops a pick that the search narrows out of view). (2) The dialog no
> longer **jumps** when a long client name appears — `.datev-file-dialog` CSS caps every control to the
> modal width (`min-width:0`, `box-sizing:border-box`).
>
> *Fixed 2026-06-18:* the keyboard-only context-menu bug (keyboard selection didn't arm the ▤ Menu /
> Shift+F10 key) — the primary row now takes DOM focus on selection ([`Tree.jsx`](webui/src/Tree.jsx)),
> and `onContextMenu` anchors at the row rect when the key supplies no pointer coords. Covered by
> `Tree.test.jsx` (focus moves to primary; input focus not stolen; coordless contextmenu still opens).

---

## Open / deferred items

### Planned changes — requested 2026-10-10 (recorded, NOT built)

Requested by Tobias while the tester kit was built. Each item changes a user-facing flow:
when it ships, update the named `manual_tests` cases and rebuild the kit in the same session.

1. **Decide "do not compress" — keep the original as a deliberate choice.** A document must be
   markable as *not to be compressed* even though smaller variants exist: the same act as
   „Lesbarkeit geprüft", but for the **original** data. Today that is impossible — with
   „unkomprimierte Fassung" selected the button is disabled (`applied` is true for an
   uncompressed node in [`PreviewControls.jsx`](webui/src/PreviewControls.jsx)), so the red
   "undecided" dot of a compressible document can never be cleared without compressing.
   The model already has `Node.no_compression` (excluded from `compression_undecided`, blocks
   `Compress`); decide whether to reuse it or add a separate "decided: original" flag —
   `no_compression` is also set by merge on a DPI conflict, and the decision must stay
   reversible (undoable, and re-openable to compress later). Tests: 03 MT-12, 06 MT-44/MT-47,
   08 MT-55.
2. **Rename the apply button: „Lesbarkeit geprüft" → „Nur diese Version behalten".** With
   item 1 it becomes one action for whichever version is shown (a compressed variant *or* the
   original). i18n: key change in `en.js` + every full-coverage language; the label is quoted
   16× in `manual_tests/*.md` and in the help texts of `help/content.js` (20 lines).
3. **DPI handling is defective — verified 2026-10-10** (repro with
   `Farbscan_Rechnung_3_Seiten.pdf` from the kit; options at 50–150 DPI = jpg + jpg_color
   (plus png at 50), 200/250 = jpg only, **300 = none**):
   - a. **A "nothing smaller" result at ONE dpi marks the document no-gain for ALL.**
     `CoreApi.compress_options` calls `_mark_no_gain` whenever the evaluated DPI yields no
     option. Evaluating 300 sets `compression_no_gain=True` (persisted) although 50–250 offer
     variants; a later evaluation at 150 returns options but the flag stays, the red dot stays
     cleared, and auto-evaluation skips the node. Fix: derive the verdict only from the
     reference DPI (or the lowest), or keep it per DPI, and clear it when any DPI finds a variant.
   - b. **Applying a method that is not offered at the current DPI is a silent no-op.**
     `_compress` returns the document unchanged when `engine.compress` yields `None` → `ok: true`,
     no undo step, no message. In the UI the slider reloads the list, the selected method can
     drop out of it, the `<select>` then *shows* „unkomprimierte Fassung" while its state still
     holds the old method, and the apply button stays clickable. Fix: on reload fall back to
     the best/original and say so; make `_compress` raise a `CommandError`.
   - c. **The slider only takes effect on mouse-up/touch-end.** Keyboard changes move the
     number but neither reload the list nor the preview; with „unkomprimierte Fassung" selected
     the slider does nothing, so the list keeps the previous DPI's sizes. The apply button then
     uses the slider value even if that DPI was never previewed.
   - d. **The DPI is not remembered per document** (the method is, via `methodMemory`); after
     re-selecting an uncommitted node the slider is back at 150 next to the remembered method.
   - e. **Compression shrinks landscape/rotated pages physically.** `CompressionConfig.max_width_pt
     = 595` scales every page wider than 595 pt: A4 landscape 842×595 pt → **595×420 pt**, image
     1228 px wide instead of 1754 (effective ~106 DPI at "150"). A portrait scan rotated with ↻
     and then compressed shrinks the same way. Fix: cap relative to the page (long edge /
     oversized MediaBoxes only) and keep the physical page size.
   - f. The upper slider range rarely helps (re-rendering above the source resolution cannot
     shrink) and an empty list is shown without explanation — add a hint instead.
   Tests: 03 MT-11, 05 MT-33, 06 MT-43; add a case for landscape pages once (e) is fixed.
4. **Auto-status on import.** As soon as **any** node of the document carries a status
   (Erfassungskennzeichen), newly imported documents get **„Zu erfassen"** automatically;
   in a document without any status, imports stay status-less (today's behaviour). Clarify
   when building: does it cover every import path (dialog, drop, archive/e-mail members) and
   what happens to statuses carried by an imported `.belegtool`. Tests: 08 MT-50 (new nodes
   have no status — becomes conditional), 01 MT-01b.
5. **Exporting a single document: no table of contents by default.** When exactly one
   **document** (leaf) is exported, „Inhaltsverzeichnis" and „PDF-Lesezeichen" (and the tag
   index) start **unchecked**; the user can still tick them. Tests: 04 MT-14 step 5,
   05 MT-36, 08 MT-58.
6. **Default file name of an export = the exported node, with its path.** Rule as stated:
   when **one node** is exported (no sibling selected at the top level of the selection — also
   for a single leaf), the suggested name is the node name, prefixed by its ancestors from the
   root down, joined with underscores: `<root>_<folder>_…_<node>.pdf` (e.g.
   `Beispielmappe_02 Bank_Darlehen_Tilgungsplan.pdf`). Whole-document export keeps the
   document name. To settle when building: whether a node directly under the root is
   `<root>_<node>` or just `<node>`; strip a trailing `.pdf` from node names before appending
   the extension; run the result through `CoreApi._safe_filename`. Today the suggestion is
   always the document name (`host.export_dialog`). Tests: 04 MT-14, 08 MT-58.
7. **Copy nodes within a document** (not only move) — e.g. **Strg + drag**, Explorer-style.
   Today a drag always moves ([`Tree.jsx`](webui/src/Tree.jsx) sets `effectAllowed = 'move'`;
   there is no copy command). Strg+click stays multi-select; the drag ghost must show the copy
   intent; the copy is a deep copy with **new node ids** (variants are keyed by id). The
   stale "deep copy" claims in README/FEATURES_REQUIRED/CLAUDE.md were removed 2026-11-04. Related, still
   deferred: cross-window copy (item 5 of the 2026-06-08 list below). Tests: 02 MT-09/MT-09b.
8. **The "external template/source" refusal must be bypassable** *(requested 2026-10-11 after a
   real document was refused: „…docx: Dokument verweist auf eine externe Vorlage/Quelle und wird
   aus Sicherheitsgründen nicht importiert")*. Today `office_via_com` refuses **every** OOXML
   file for which `converters.scan_ooxml_external_targets` finds a non-hyperlink
   `TargetMode="External"` relationship to an http(s)/ftp/`file:`/UNC target — with no override.
   That also hits ordinary documents: Word stores the **attached template** of a document
   created from a template on a local or network path exactly this way
   (`word/_rels/settings.xml.rels` → `attachedTemplate` → `file:///…` or `\\server\…`), so a
   harmless report cannot be imported at all. The guard itself stays justified (Word resolves a
   UNC/HTTP template on open → NTLM-hash leak / SSRF before the COM guards apply). Options, in
   order of preference:
   - a. **Neutralise instead of refuse:** convert a temp copy with the offending relationship
     removed (for `attachedTemplate` also the `<w:attachedTemplate>` element in `settings.xml`;
     Word falls back to Normal.dotm, the document keeps its own styles). No network access, no
     prompt. For linked *content* (linked images/OLE) the linked part is then missing → say so
     in a notice.
   - b. **Explicit override:** offer „Trotzdem importieren" per file, showing the target; keep
     the hard refusal (or a much stronger warning) for http/UNC targets, where the risk is real.
   - c. In either case **name the target in the message** (today it is only written to the log),
     so the user can see what the document points at.
   Workaround until then: open the file in Word and save it as PDF, then import the PDF.
   Tests when built: 01 MT-05 (its note says such files are refused), 01 MT-03c; add a sample
   `.docx` with an attached-template relationship to `scripts/testkit/samples.py`.
   **Also the chosen way to duplicate a folder with its sub-structure** (decided 2026-10-10 for
   the ESt filing structure: a second rental property = a copy of the „Objekt" folder, empty
   sub-folders included) — so copying a folder that holds no pages must work.
8. **„Neu aus Vorlage" (document templates) — deferred 2026-10-10.** A folder-only `.belegtool`
   already saves and opens (probed through `PDFStorage` and `CoreApi.open`, not in the UI), so
   a template file is possible today; what is missing is opening it as a NEW unsaved document,
   so that „Speichern" cannot overwrite the template. Not planned yet.

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
    (archive → mail → attachment). Recursion is bounded by **`_ARCHIVE_MAX_DEPTH = 10`** (3 until v3.11.2; anti
    zip-quine → „zu tief verschachtelt"), and the bomb caps are now a **shared `_Budget`** (decoded
    bytes + member count) threaded through every level, so nesting can't compound past
    `infra.limits.BOMB_CAP_BYTES`/`BOMB_CAP_ENTRIES`. A corrupt/oversized inner container degrades to
    „nicht importierbar" without aborting the import. Tests: `packages/belegtool-archives/tests/test_archive_nested.py` (9 cases:
    cross-kind recursion, depth bound, shared byte+member budget, corrupt-nested degrade); existing
    `test_archive_*` unchanged. (Logged from the 2026-06-16 audit, finding #6; extended to nested
    mail 2026-06-26.)
    **Follow-up (2026-06-26): archive subfolders are now honored as folder nodes.** A zip/tar
    member path like `rechnungen/2024/beleg.pdf` builds `Ordner rechnungen › Ordner 2024 ›
    beleg.pdf` (helpers `_split_member_path`/`_ensure_folder`/`_insert_by_path` in `archives.py`),
    merging siblings under shared folders — fixing the old zip **path-in-the-leaf-name** and the tar
    **basename-flatten** (which also dropped same-named files in different folders). Composes with
    the nesting above (a container at `sub/inner.zip` → `Ordner sub › Ordner inner.zip › …`). Tests:
    `packages/belegtool-archives/tests/test_archive_subfolders.py` (6).
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
  the **DATEV write-back parallel local save** (`datev_save_back`) snapshots `edited` before the
  network round-trip but the in-sync local `.belegtool` save re-reads the *current* session
  document afterwards — a concurrent same-session edit between the two would diverge DATEV (old
  bytes) from the local file (new bytes); unreachable because the write-back runs under the
  modal busy-state that disables edits (single-window UI), annotated at the call site;
  `_safe_change_dt`/reopened-baseline use an extra `get_document` round-trip whose failure is
  fail-safe (the next write-back re-establishes the baseline from the server);
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
  `from_recursive_array`, the data properties, `_concat_children_data`, `is_valid`;
  `copy` removed 2026-11-04 with its only caller `export_selection`, I-2).
  The redundant PDFNode-op unit tests were dropped (the operations live in and are tested
  through `core/engine`/`core/commands` — `test_split_merge`, `test_engine_commands`, …);
  [`test_belegtool_roundtrip`](tests/test_belegtool_roundtrip.py) guards the carrier.
- **Headless import is bytes-only end to end** — plain-PDF *and* archive/email
  paths store bytes only (the carrier never renders); page count uses pikepdf (`len(pdf.pages)`);
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
  ⚠ **Multicore caveat:** every pdfium call is serialized by a process-wide priority lock (and it was GIL-limited ~1.2× under PyMuPDF), so this
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
`t('…')` key), [`en.js`](webui/src/i18n/en.js) is the **canonical full key set** (**218 keys** —
the v3.9 base of 163 strings plus the DATEV v3.10/v3.11 additions: mode toggle, no-connection guard,
filing dialog, Bezeichnung, checked-out-self notice; the exact count is asserted by `i18n.test.js`
(`Object.keys(en).length === 218`), which also asserts every full-coverage language's
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
- **Completeness (2026-06-08):** **19 languages are 100% (all pre-2026-11-04 keys, incl. error messages; the 9 QS load/export-integrity keys are de+en pending batch)** — de (source),
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
- **Version `3.11.4`** (bug form default + BETA_TESTING heading) → keep in sync with `version_info.py`.
- **Windows 10/11 only**; **Office-via-COM** caveat for Word/Excel/PPT import.
- **One known gap that must NOT be reported as a bug** (the bug form's required
  checkbox enforces this): compression irreversible after save ("bereits komprimiert
  (keine Quelle)"). The former auto-split gap was removed when #13 (configurable
  export split) shipped on the v3.10 branch. **If this gap is fixed, remove it from
  the checkbox, BETA_TESTING.md §4, and CONTRIBUTING.md** — otherwise testers are
  told a working feature is broken.
- **Manual tests `00`–`10` are German and describe the current UI** (rewritten 2026-10-10
  against the source; UI labels checked against `en.js` and the components). Testers get the
  generated kit `manual_tests/testpakete/` (one PDF + sample files per case) — BETA_TESTING.md
  §2/§3 point there.
- **Three install paths**: Microsoft Store (live since 2026-06-08, Store ID `9PL4D25N00XD`,
  guide `docs/Installation_Microsoft_Store.pdf` — **may lag the repo version**), prebuilt
  onedir zip from GitHub Releases, and from source (Python 3.12+ + Node, `pip install -r
  requirements.txt`, `cd webui && npm install && npm run build`, `python host.py`).
- **Fixtures in `tests/data/input/`** (regen `python tests/make_fixtures.py`).
- The `config.yml` and template links hardcode the repo URL
  `tobiasheinrichfaska/DigitalerUnterlagenOrdner` and the `master` branch.

⚠️ **Manual GitHub steps (not in the repo):** Discussions must be enabled in repo
**Settings → Features**, and a Release published (or the build folder zipped) for
the prebuilt download path to work.
