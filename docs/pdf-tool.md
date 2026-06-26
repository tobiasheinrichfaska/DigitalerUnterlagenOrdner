# PDF-Tool surface — design

> **Status:** design + step-1 spike **passed**. Branch `feat/pdf-viewer-surface`.
> **Decision (2026-06-26):** add a **second front-end surface** ("two UIs") inside the
> existing BelegTool app — a **PDF-Tool** (PDF.js-based viewer *and editor*) — on the
> **same shared Python core** as the organizer. Not a separate app; not a retrofit of the
> raster preview. It is a **tool**, not a read-only viewer: edits (OCR text, filled forms,
> page rearrangement) are **persisted permanently** to whatever it is bound to.

## Goal

Make BelegTool able to *view and edit* a PDF richly. Target capabilities:

- **Text selection / copy** and **in-page search**
- **OCR** (make scans searchable/selectable)
- **Page rearranging** (within the bound PDF)
- **Compression**
- **Form filling** (AcroForm)
- **Signing** — **deferred** (see Signing)

## Why two surfaces (not one pane, not two apps)

The deciding factor is the **rendering model**. The existing preview is server-rendered
**raster PNGs** (`services/render.render_pdf_to_pngs` → virtualized `<img>` in
`Preview.jsx`). Selection / search / forms need a **live, structured PDF in the UI**, which
is what **PDF.js** provides (canvas + text layer + AcroForm/annotation layer). The
byte-level features (rearrange, compress, export) are **UI-agnostic Python** already built
in BelegTool's core.

- Retrofitting select/forms onto the raster pane → reimplementing PDF.js worse. ✗
- A separate app → rebuild the host/build/packaging + duplicate the core. ✗
- **Two surfaces on one shared core** → PDF.js does viewing/interaction; Python does byte
  transforms; the existing engine is reused. ✓

## Step-1 spike result (PASSED, 2026-06-26)

A minimal PDF-Tool surface (`webui/pdf-tool.html` + `src/pdftool/main.js`, Mozilla's
`pdfjs-dist/web/pdf_viewer.mjs`) was proven in **real Chromium = the WebView2 engine** via
`webui/e2e/pdftool.spec.js`:

- ✅ **Selectable text layer** — `.textLayer` renders the sample text and `getSelection()`
  returns it after a triple-click.
- ✅ **Interactive AcroForm** — the form field renders as an `<input>` and accepts a value.
- ✅ **Vite multi-page build** emits `dist/index.html` + `dist/pdf-tool.html`; the heavy
  PDF.js chunk (~584 KB) lands **only** on the pdf-tool surface (organizer bundle untouched).
- ✅ No regression: all 4 e2e specs pass.

So the rich-interaction features the raster organizer can't do are confirmed feasible here.
(Sample: `webui/public/spike-form.pdf`, generated with reportlab — selectable text +
one AcroForm text field.)

## Architecture

```
pywebview host (one process)
  └── CoreApi  (one shared Python core: engine, commands, compress, export, OCR, sign)
        ├── surface A: organizer  — existing React SPA, raster preview (UNCHANGED)
        └── surface B: PDF-Tool   — NEW, PDF.js: text layer, AcroForm, search, print, edit
```

- **Two Vite entry points** → `index.html` (organizer) and `pdf-tool.html` (PDF-Tool).
- The host picks the surface and the **binding** by **launch context** (below). Both windows
  share one in-process `CoreApi`.

### Capability → mechanism

| Capability | Where it runs | Mechanism |
|---|---|---|
| Text select / copy / search | client (PDF.js) | text layer + find controller — built in |
| Links / print | client (PDF.js) | annotation layer + native print |
| Form fill (AcroForm) | client render + Python save | PDF.js widgets; values written back via pypdf/PyMuPDF |
| OCR | server (Python) | `ocrmypdf`/Tesseract → searchable PDF (text layer) |
| Page rearrange | server (Python) | reuse `core/engine` page ops on the bound bytes |
| Compression | server (Python) | reuse `formats/compress_pdf_bytes` |
| Export | server (Python) | reuse `formats/toc_export` |
| Signing | — | **deferred** (client remote-signing via a QTSP; see Signing) |

## Binding & persistence model (decided 2026-06-26)

The PDF-Tool **binds** to a target by launch context, and edits persist **permanently** to
that target. Three contexts:

| Launched… | Binds to | UI | Persistence |
|---|---|---|---|
| **with a `.pdf`** | that **PDF file** | PDF-Tool | edits written **back into the `.pdf`** |
| **with a `.belegtool`** (or no args) | the **belegtool** | organizer | as today (save the belegtool) |
| **from a node** ("Im PDF-Tool öffnen") | that **node** (locked) | PDF-Tool | edits written **back into the node** → belegtool dirty → persisted on belegtool save |

Rules:

1. **PDF binding** — opening a `.pdf` directly (file association / "öffnen mit" /
   `BelegTool.exe x.pdf`) routes to the PDF-Tool and binds to the file. OCR / form-fill /
   page-rearrange **overwrite the source `.pdf`** (permanent). *(This intentionally
   reverses the earlier "force Save-As" idea — the PDF-Tool is an editor, not a viewer.)*
2. **Node binding + lock** — "Im PDF-Tool öffnen" on a tree node **locks the node** (a
   node-level exclusive edit, analogous to the existing file lock) and binds the PDF-Tool to
   it. While locked:
   - the organizer may **reposition** the node (move/reorder in the tree) freely — that
     does not touch content;
   - if the organizer tries to **change the node's content** (compress / split / rotate /
     merge / delete) → **warn**, and offer **(a) don't change** (cancel the op) or
     **(b) break the binding** (release the lock; the organizer op proceeds; the PDF-Tool
     goes read-only / its unsaved edits are dropped).
3. **Save-back on close** — closing a node-bound PDF-Tool with unsaved edits **prompts
   "zurück in den Knoten speichern?"**. Saving writes the edited bytes into the node (a
   content change → marks the belegtool dirty; the user persists it with the normal save).

### OCR × compression (decided 2026-06-26)

OCR adds an **invisible text layer** over the page image. This interacts dangerously with
BelegTool's compression, so the rules are:

1. **OCR runs on the uncompressed original** (best resolution → best accuracy). Never OCR a
   lossy/low-DPI result.
2. **The OCR text layer must survive compression.** BelegTool's current image methods
   **rasterize the whole page**, which would **silently drop the text layer**. So for an
   OCR'd page, compression must switch to a **text-layer-preserving** method: recompress only
   the **image streams** (downsample / re-JPEG) and keep the invisible text objects (cf.
   `ocrmypdf --optimize`, pikepdf/mutool). It only re-encodes the image, so the text stays
   aligned.
3. **Warn/block, don't predict.** The deterministic guard: if a chosen compression method
   would **drop an existing OCR text layer**, **warn or block** and steer to the preserving
   method. We do **not** build a "would it still OCR correctly?" quality gate (re-OCR +
   confidence compare) — over-engineering, since a preserved layer never needs re-OCR. Surface
   **"OCR-Textebene erhalten ✓/✗"** in the existing human "Lesbarkeit geprüft" step instead.

Net: **OCR first → text-preserving compression on OCR'd docs → warn/block layer-dropping
methods.** Needs a structural image-recompress method added to / selected in
`compress_pdf_bytes` for OCR'd nodes (step 4/5).

### Interaction with the existing source/compression model (open item)

Writing edited bytes back into a node is a content change. It must reconcile with BelegTool's
drop-source-on-save / "committed node" semantics (`core/model`, `formats/pdf_storage`): does
a PDF-Tool edit reset `is_compressed`/`compression_no_gain`, drop variants, re-evaluate? The
safe default: treat a PDF-Tool save as **new source bytes** for the node (clear compression
state, like rotate does today). Confirm in step 3/4.

## Decisions

1. **PDF.js** is the PDF-Tool engine (proven in the spike).
2. **Two distinct surfaces**, one shared Python core — never one pane doing both.
3. **Bind + persist permanently** to the launch target (pdf file / belegtool / node), per
   the table above — *not* read-only, *not* forced Save-As.
4. **Node binding locks the node**; content-change conflicts warn + offer cancel/break-bind;
   close prompts save-back.
5. **OCR is an optional/on-demand component** (Tesseract/Ghostscript are large) — not
   bundled into every install. PDF.js is lazy-loaded only on the PDF-Tool surface.
6. Reuse rearrange/compress/export from the existing engine.

## Signing — DEFERRED (2026-06-26)

**Decision: not built now.** Recorded so the chosen direction survives the gap.

- **We do NOT sign documents ourselves**, so local certificate signing (pyHanko) is **out of
  scope** — no signing cert to buy, no local-sign UI.
- **Adobe Acrobat Sign (cloud)** is rejected as a default: it uploads documents to Adobe's
  **US** cloud — wrong for Belege / client tax documents under DSGVO.
- **The actual goal is letting CLIENTS sign without special software** — which inherently
  needs a remote-signing **service** (our app runs on our desktop, not the client's).
- **Chosen direction when revisited: D-Trust *sign-me*** (Bundesdruckerei; German **QTSP**
  on the EU Trusted List). Clients reach a **QES** (legally = handwritten) **from a browser +
  phone**: one-time identification via **eID/AusweisApp** or Video-Ident, then sign in the
  browser (key in D-Trust's remote HSM/QSCD — no card reader, no PC software). **German
  hosting**, AVV available → DSGVO fit; the returned PAdES QES validates green in Acrobat
  (D-Trust ∈ AATL/EUTL). Integration: **(A) link-out / portal first**, **(B) sign-me API**
  later. Strictly **opt-in + DSGVO-disclosed** (the document leaves the machine to D-Trust/DE).
- **Open questions for D-Trust (when revisited):** current pricing (per-signature vs.
  contract), API scope (session creation, callbacks/polling, return of the signed file),
  AVV terms.
- Note: browsers/our PDF.js do **not** validate signatures — only Acrobat/Reader (and the EU
  DSS validator) do. A *visible* signature appearance is cosmetic, not cryptographic.

## Host routing

- **`.pdf` on the command line / association** → extend
  [`host._startup_path_from_argv`](../host.py) to accept an existing `.pdf` and launch the
  PDF-Tool bound to it. (Today it only honours `.belegtool`.)
- **From the tree** → "Im PDF-Tool öffnen" opens the PDF-Tool for a node in a **new window**
  (reusing the `new_window` / `open_view_in_new_window` plumbing), locking the node.
- New bridge methods: `get_pdf_bytes(target)`, `save_pdf(target, bytes)` (pdf-file or node),
  `ocr(target)`, `sign(target, certRef)`; node lock/break-bind via the session.

## Step sequence

0. Branch + this doc. ← *done*
1. **Spike (PDF.js text-select + AcroForm in WebView2).** ← *done, PASSED*
2. **Host routing + binding model.** Launch-context binding (pdf / belegtool / node), node
   lock, conflict warning, save-back-on-close; `get_pdf_bytes`/`save_pdf` bridge.
3. **Reuse core ops** (rearrange/compress/export) on the bound bytes; reconcile the
   source/compression model for node save-back.
4. **Form-fill round-trip** (persist AcroForm values via pypdf/PyMuPDF; reopen check).
5. **OCR (optional component).** *(Signing is deferred — see Signing.)*
6. **Tests + docs + manual_tests + version bump + package.**

## Open questions / risks

- **Node save-back vs compression/source model** (above) — reconcile in step 3/4.
- **Bundle size & identity** — keep OCR optional; PDF.js chunk lives only on the PDF-Tool
  surface. Revisit Store positioning if scope drifts from "organize Belege".
- **AcroForm round-trip fidelity** (appearance streams); **XFA out of scope**.
- **Signing trust** — local pyHanko needs the user's cert; AATL/eIDAS validity depends on
  the cert chain, not on us.

## Reuse inventory

`core/engine.py`, `core/commands.py`, `formats/compress_pdf_bytes.py`,
`formats/toc_export.py`, the pywebview host + per-window `HostApi`, `new_window` /
`materialize_subset`, i18n, `build.ps1` / `belegtool.spec` / `packaging/` (MSIX).
