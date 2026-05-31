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

**React UI in a thin native WebView2 shell + one long-lived per-user Python "core".**
**No server** — UI and core talk over a **per-user named pipe** (nothing listens on a
network port). Packaged as one desktop app.

```
   (per Windows user / RDS session)
┌──────────────────────────┐   per-user named pipe (local IPC, no port)   ┌───────────────────────────┐
│  WebView2 shell window(s) │ ───────────────────────────────────────────▶│  Python CORE (one per user) │
│  React SPA (Vite)         │ ◀─────────────────────────────────────────── │  session mgr + worker pool  │
│  tree · preview · toolbar │   JSON tree + PNG/PDF blobs (messages)        │  core + services (reused)   │
└──────────────────────────┘                                              └───────────────────────────┘
        native window, file dialogs,                              warm: survives UI close,
        drag-drop, file association                               idle auto-shutdown (~5–10 min)
```

**Properties (agreed):**

- **No server.** The shell calls Python directly through the WebView2 ↔ host bridge
  / a **per-user named pipe** — no HTTP, no open socket. (FastAPI loopback is kept only
  as an *option* if a real browser / remote / multi-front-end is ever wanted — §4.)
- **Native UX.** The shell gives a real OS window, native open/save dialogs, drag-and-drop
  and file association; the React app just draws inside it. The user can't tell it's web tech.
- **Warm core.** The Python core **keeps running after the UI window closes**, so the next
  open is near-instant (interpreter + native libs already loaded). It **idle-auto-shuts-down**
  after ~5–10 min with no window, to free RAM. Optional "keep in tray / autostart" setting
  for an instant first open.
- **One core serves many files for the same user** — it's a **document/session manager**
  (each window ↔ one document, shared render cache) with a **process worker pool**
  (`multiprocessing`) for CPU-bound ops (render/compress/export). Process workers give real
  parallelism around the GIL **and** crash isolation; they also sidestep the non-thread-safe
  bits of `fitz`/`pikepdf`.
- **One core *per user* (RDS-safe).** Each Windows user / RDS session gets its **own** core,
  running **as that user**, with a **SID-scoped named pipe**. Users are fully isolated
  (memory, temp dirs, file ACLs) — required for privacy/DSGVO. See §2a.
- The React app never touches PDFs directly; it asks the core to open/save, import,
  compress, split/merge, export, and **render previews to PNG**. No PDF logic is rewritten in JS.

**Rejected alternatives:**

- **Pure-JS browser port** (pdf.js/pdf-lib) — too lossy (no Office/COM, no HEIC, different
  compression) and a large rewrite.
- **One shared core for all users** — would commingle users' documents and run as one
  identity (wrong file ACLs); a correct shared backend would need a full authenticated
  multi-tenant server with sandboxing/impersonation: overkill, risky, DSGVO minefield.

### 2a. Concurrency & multi-user model

| Scope | Model |
|---|---|
| Same user, N files / windows | **one shared core** — session manager + process worker pool; shared preview cache |
| Different users (RDS / multi-user host) | **one core *per user*, as that user, in their session, SID-scoped named pipe**; independent idle-shutdown |

Library-safety note: PyMuPDF (`fitz`) and `pikepdf` are not safe to share objects across
threads — keep heavy ops in **separate worker processes**, the core itself stays I/O-light
and responsive.

### 2b. User-experience parity (it behaves like a normal app)

| Action | Works? | How |
|---|---|---|
| Double-click a `.belegtool` → opens | ✅ | exe is the file-type handler; gets the path on `argv`, opens/attaches a window |
| Save (same file) | ✅ | core already has the path; Ctrl+S writes back, no dialog |
| Save as… / Close | ✅ | native Windows save dialog; normal close with "unsaved changes?" |
| Export | ✅ | core builds the PDF, writes to a path picked in a native dialog |
| Import by dragging files in | ✅ | dropped file's **bytes + name** go to the core to import |

First launch pays a one-time ~1–3 s Python start; subsequent opens hit the warm core and
feel instant.

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
| 2. Core service (no server) | one per-user Python core: open/save `.belegtool`, import file, tree CRUD (split/merge/folder/rename/delete/move), compress, export, **render preview → PNG**; **session manager** (multi-document) + **process worker pool**; **idle auto-shutdown** | reuses `core`+`services`; talks over a **SID-scoped named pipe** (RPC-style messages), **no HTTP/port**. A FastAPI loopback adapter is an *optional* extra if a real browser/remote client is ever needed |
| 3. React SPA (Vite) | tree view, preview pane, toolbar, status colours, the critical flows from `FEATURES_REQUIRED.md` | drag-drop, context menu; previews are `<img>` of PNG blobs from the core |
| 4. Desktop shell + packaging | thin **WebView2 shell** (file-association entry, native dialogs, drag-drop) that starts/attaches the warm per-user core; bundle core + React build into one installer | shell: compiled host (Rust/C#/Go) **or** `pywebview`; **single-instance** coordination per user; Electron only if cross-platform later |
| 5. Parity & cutover | manual_tests pass against the React app; keep Tk app until parity | both front-ends can share the same core during transition |

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
| **In-page (serverless)** | host reads the bytes and `PostWebMessage`s them into WebView2; JS processes in-page (pdf.js / pdf-lib / WASM) | **pure-JS** apps — no server, no Electron, tiny |
| **Named-pipe core (no server)** | host passes the path to the **per-user Python core** over a named pipe; the core loads it and returns the JSON tree + PNG previews | **this app** — native Python engine must process the file, but still **no HTTP/port** |
| FastAPI loopback | host opens the app at `http://127.0.0.1:PORT/?open=<path>` | only if a real browser / remote client is also wanted |

➡️ **BelegTool → named-pipe core:** the shell is the file-association entry; it starts or
attaches the **warm per-user core** and opens a WebView2 window → React app → core `open(path)`.
**No server, no port.** Serverless-in-page is impossible here because the PDF engine is native.

➡️ **A pure-JS project → in-page:** double-click → mini exe → bytes posted into the page,
zero server, no Python. Reach for **Electron only** if you need cross-platform + deep
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
   `refactor/headless-core`; it’s low-risk, test-guarded, and useful on its own
   (it lands on `master` and helps the current app even if React is dropped).
2. Adopt the **React UI in a WebView2 shell + one warm per-user Python core**, talking
   over a **per-user named pipe (no server, no port)**. Core = session manager +
   process worker pool, with idle auto-shutdown. **Do not** attempt a pure-JS rewrite,
   and **do not** share one core across users (RDS isolation).
3. **Office import is decided** (keep via the Python core, Windows COM); LibreOffice is a
   *Future idea*. Remaining calls before Phase 4: shell tech (compiled host vs `pywebview`)
   and the "keep warm in tray / autostart" default.
