# React-on-PC Migration Plan — DigitalerUnterlagenOrdner

Goal: bring the BelegTool to a **React UI on the PC**, and as the foundation,
**cleanly divide GUI from data/storage/processing** so the logic can be reused
behind a different front-end.

Status: planning. This document lives on the `react-migration` branch.

---

## 1. Current architecture (assessment)

| Layer | Files | Notes |
|---|---|---|
| GUI (Tkinter/ttk) | `belegtool_main.py`, `panel_controls.py`, `view_tree.py`, `view_preview.py`, `status_display.py`, `preview_page.py` | Windows-native ttk; event/menu wiring; preview canvas |
| "Model" | `pdf_node.py` (`PDFNode`), `pdf_storage.py` (`PDFStorage`) | tree, status, `.belegtool` (PDF + embedded `/JSONStructure`) |
| Processing | `compress_pdf_bytes.py`, `universal_importer.py`, `toc_export.py`, `tools.py` | compression, import, export, sanitize |

### The coupling problem (why a port is not trivial)

`PDFNode` is supposed to be the data model but it is entangled with **view +
runtime** concerns:

- imports `fitz` (PyMuPDF) and `PIL.Image` → **renders preview images itself**;
- imports `threading` → runs **background compression/preview tasks** (`compress_lazy`, `compress_multi_lazy`, `preview_lazy`);
- imports `preview_page.PreviewPage` → which imports **`PIL.ImageTk`** (a Tk object) → the model holds **Tk-bound image objects**;
- imports `status_display` → which imports **`tkinter`** → the model reaches into the GUI to register "busy" tasks.

So today the "model" transitively depends on **Tkinter, image rendering, and
threading**. None of that is portable.

### The native-dependency reality (drives the target architecture)

The PDF engine is **native CPython**, not browser-portable:

- `PyMuPDF` (fitz), `pikepdf`, `pypdf`, `reportlab`, `Pillow`, `pillow-heif`, `xhtml2pdf`, `extract-msg`
- **`pywin32` COM** for Office (Word/Excel/PPT) conversion — **Windows-only**.

➡️ A pure browser/JS React app (the workspace's usual single-file-HTML desktop
deploy) **cannot** reproduce this without a large, lossy rewrite (pdf.js +
pdf-lib, no Office/COM, no HEIC, different compression). **The Python processing
must be kept and reused behind the React UI.**

---

## 2. Target architecture

**React SPA front-end + local Python "core" back-end**, packaged as one desktop app.

```
┌─────────────────────────┐     HTTP / WebSocket (localhost)     ┌──────────────────────────┐
│  React SPA (Vite)        │ ───────────────────────────────────▶│  Python backend (FastAPI) │
│  tree, preview, toolbar  │ ◀─────────────────────────────────── │  core + services (reused) │
└─────────────────────────┘   JSON tree + PNG/PDF blob endpoints  └──────────────────────────┘
        rendered in a desktop webview (pywebview / Tauri / Electron)
```

- The React app never touches PDFs directly; it calls the backend for open/save,
  import, compress, split/merge, export, and **preview rendering returns PNG bytes**.
- The backend reuses the existing (decoupled) Python services — no PDF logic is
  rewritten in JS.

**Rejected alternative:** pure-JS browser port (pdf.js/pdf-lib). Too lossy
(no Office/COM, no HEIC, different compression fidelity) and a large rewrite.

---

## 3. Phase 1 — Decouple core from GUI (do this first; it stands on its own)

Re-layer the repo so the domain + processing have **zero** Tk/Tk-image/threading
dependencies. This is the "better divide GUI and data storage" the migration needs,
and it improves the current Tkinter app's testability immediately.

Proposed layout (Python package, no behaviour change to the Tk app):

```
core/        # pure domain — no fitz, no PIL, no threading, no tkinter
  node.py        # PDFNode: tree, status, metadata, page-byte refs, to_dict/from_dict
  belegtool.py   # .belegtool read/write (PDF + /JSONStructure)  (from pdf_storage)
services/    # stateless operations: bytes in -> bytes out, native deps OK, NO UI
  compress.py    # = compress_pdf_bytes
  importer.py    # = universal_importer; Office/COM behind a ConverterPort interface
  export.py      # = toc_export
  render.py      # NEW PreviewRenderer: pdf bytes -> PNG bytes (was inside PDFNode)
  sanitize.py    # = tools
app_tk/      # current GUI, rebuilt on core+services
  views...       # view_tree / view_preview / panel_controls / main
  tasks.py       # thread-pool task runner (was the threading inside PDFNode)
  imagetk.py     # PNG bytes -> ImageTk for the canvas (was preview_page)
  status.py      # busy/status display (Tk)  (was status_display)
```

Concrete decoupling steps (each is a small, test-guarded PR):

1. **Preview out of the model.** Move fitz-render-to-image out of `PDFNode` into
   `services/render.py` returning **PNG bytes**. The Tk view converts PNG→ImageTk;
   a React view will use `<img src=…>`. Remove `PIL.ImageTk` / `preview_page` from the model.
2. **Threading out of the model.** Move `compress_lazy` / `compress_multi_lazy` /
   `preview_lazy` into `app_tk/tasks.py`. The core exposes only **synchronous pure
   ops** (`compress(bytes) -> bytes`, `render(bytes) -> png`).
3. **Status port.** Replace `status_display.register_task` calls in the model with
   an injected callback/observer (a `ProgressPort`). Tk app supplies a Tk impl;
   the backend supplies a no-op/WS impl. Removes the `tkinter` import from the model.
4. **Isolate Windows/COM.** Put Office conversion behind `services/importer.ConverterPort`
   so the core has no hard `win32com`/`pythoncom` dependency at import time.
5. **Lock the data contract.** Document the `.belegtool` format and the
   `to_dict`/`from_dict` JSON schema as the **interchange contract** (it becomes the
   HTTP payload shape). Add round-trip tests (already partially covered).

Exit criteria for Phase 1: full `pytest` suite + `manual_tests/` still green with
the Tkinter app running on the new `core` + `services`. **Merge to `master`.**

---

## 4. Phases 2–5 — the React app

| Phase | Deliverable | Notes |
|---|---|---|
| 2. Backend API | FastAPI exposing services: open/save `.belegtool`, import file, tree CRUD (split/merge/folder/rename/delete/move), compress, export, **render preview → PNG** | reuses `core`+`services`; runs on localhost |
| 3. React SPA (Vite) | tree view, preview pane, toolbar, status colours, the critical flows from `FEATURES_REQUIRED.md` | drag-drop, context menu; previews are `<img>` from the render endpoint |
| 4. Desktop packaging | one launchable app: webview shell + bundled Python sidecar | **pywebview** or **Tauri (Python sidecar)**; Electron is the heavy fallback |
| 5. Parity & cutover | manual_tests pass against the React app; keep Tk app until parity | dual front-ends share one backend during transition |

The existing `manual_tests/` double as the **acceptance suite** for the React app.

---

## 5. Branching strategy

- Keep **`master` shippable (Tkinter)** the whole time.
- `react-migration` (this branch): holds this plan + the layout skeleton.
- Work in small branches off `master`, merged as they go green:
  - `refactor/headless-core` → Phase 1 (decouple). **Merge to master** (low risk, big payoff).
  - `feat/python-api` → Phase 2.
  - `feat/react-spa` → Phase 3.
  - `feat/desktop-packaging` → Phase 4.
- The React UI only replaces Tkinter once it reaches parity; until then both run on the same backend.

---

## 6. Risks & open decisions

| Topic | Status |
|---|---|
| **Office import** | **DECIDED:** keep via the Python backend (Windows COM). A cross-platform headless converter (LibreOffice) is parked in *Future ideas*. |
| **Webview shell / file-association** | See *Distribution & file-opening* below. Leaning: WebView2 + tiny native host (no Chromium bundle). |
| **Distribution size** | bundling Python + native PDF libs is large — acceptable for a desktop tool, but confirm. |
| **Scope of Phase 1 first** | Recommended: do the decoupling now and merge to master even if React is deferred — it pays off immediately (testability, clarity). |

### Phase 1 is valuable even if React is abandoned ("branch back")

Phase 1 (decoupling) is **not** disposable migration scaffolding. It lands on
`master` and improves the **current Tkinter app**: a pure `core`/`services` that is
testable without a display, fewer model-level races (the threading/preview coupling
behind bugs already fixed), and a clear data contract. If the React effort is later
dropped, the decoupling stays and keeps paying off. Only **Phases 2–5** (FastAPI
backend, React SPA, packaging) are React-specific and can be discarded with no loss
to the shipped Tkinter app.

### Distribution & file-opening (double-click a `.belegtool`)

Key facts:

- **Pure `file://` HTML cannot open a file by path.** The browser sandbox only allows
  manual `<input type="file">` / drag-drop (you get *bytes*, not a path) and cannot
  auto-open on double-click. (Single-file bundles still *run* under `file://` — that's
  a separate concern.)
- **File System Access API** (`showOpenFilePicker`/`showSaveFilePicker`, real
  read/write handles) needs a **secure context — `https` or `http://localhost`, not
  `file://` — and is Chromium-only.** Works for a *localhost-served* app, not a bare file.
- **OS file association launches an EXE** with the path as `argv` — a browser can't be
  the target of a path handoff. So a tiny **native entry point** is required to bridge
  the path into the page.

**The "ultra-fast mini exe hands the file to local HTML" pattern (recommended):**
a small compiled host (Rust / C# / Go — single-digit MB, starts in ms) using
**WebView2**, the Edge runtime **pre-installed on Windows 10/11 (no Chromium to
bundle)**. On double-click it gets the path as `argv` and hands it to the page one of
two ways:

| Variant | How the file reaches the page | When |
|---|---|---|
| **Serverless** | host reads the bytes and `PostWebMessage`s them into WebView2; JS processes in-page (pdf.js / pdf-lib / WASM) | **pure-JS** apps — no server, no Electron, tiny |
| **Loopback** | host starts the local Python backend, opens the app at `http://127.0.0.1:PORT/?open=<path>`; the page calls the backend to load it | **this app** — native Python engine must process the file |

➡️ **BelegTool → loopback:** mini exe = file-association entry + launches the Python
backend (sidecar) + opens a WebView2 window → React app → `POST /open {path}`.
Serverless is impossible here because the PDF engine is native.

➡️ **A pure-JS project → serverless:** double-click → mini exe → bytes posted into the
page, zero server. Reach for **Electron only** if you need cross-platform + deep
Node/OS integration; for Windows-only, WebView2 + a tiny host is far smaller/faster.

---

## 7. Future ideas

- **Headless Office conversion (LibreOffice).** Replace the Windows-only COM path with
  a bundled/headless LibreOffice (`soffice --headless --convert-to pdf`) so Word/Excel/
  PPT import works **cross-platform** and without Office installed. Trade-offs: large
  bundle, slightly different rendering fidelity, process management. Parked until the
  backend exists and cross-platform is actually needed.

### Recommendation

1. **Start with Phase 1** (decouple core/services from Tk/threading) on
   `refactor/headless-core`; it’s low-risk, test-guarded, and useful on its own.
2. Adopt the **React + local Python backend** architecture; package with
   **pywebview** (or Tauri) — do **not** attempt a pure-JS rewrite.
3. Decide the Office-conversion strategy before Phase 2 (it shapes the backend).
