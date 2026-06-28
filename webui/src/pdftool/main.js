// PDF-Tool surface (see docs/pdf-tool.md). Renders the BOUND PDF and lets the user
// add text (FreeText / typewriter) and fill forms, then save it back into the node:
//   PDF.js saveDocument() bakes the additions in as real FreeText annotations + form
//   values → bytes → bridge.save_node_back(session, b64) → SetNodeBytes on the node.
// Self-authored text round-trips: reopening the node loads the annotations back into
// the editor as editable objects (PDF.js re-loads its own annotations).
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { EventBus, PDFViewer, PDFLinkService } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'
import { chooseSource, base64ToUint8, uint8ToBase64, datevAction } from './source.js'
import { datevSavedNotice, datevVerdictKey } from '../lib/datev.js'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const container = document.getElementById('viewerContainer')
const eventBus = new EventBus()
const linkService = new PDFLinkService({ eventBus })
const pdfViewer = new PDFViewer({
  container,
  eventBus,
  linkService,
  // ENABLE_FORMS renders AcroForm widgets as interactive HTML inputs;
  // annotationEditorMode=NONE turns the editor infrastructure ON in selection mode
  // (so we can switch to FREETEXT) without starting a tool.
  annotationMode: pdfjsLib.AnnotationMode.ENABLE_FORMS,
  annotationEditorMode: pdfjsLib.AnnotationEditorType.NONE,
})
linkService.setViewer(pdfViewer)

// Signal flags the e2e spec waits on (cheaper than guessing timings).
eventBus.on('textlayerrendered', () => { window.__viewerTextLayerReady = true })
eventBus.on('annotationlayerrendered', () => { window.__viewerFormLayerReady = true })

// State for the save-back wiring.
let bridge = null
let boundSession = null
let pdfDoc = null
let sourceMode = null        // 'session' | 'bridge' | 'url' — DATEV UI only for a 'bridge' .pdf
let datevConnected = false   // the open .pdf is a DATEV checkout (provenance from its path)

const textBtn = document.getElementById('btn-text')
const saveBtn = document.getElementById('btn-save')
const datevBtn = document.getElementById('btn-datev')
const statusEl = document.getElementById('pdf-status')
const setStatus = (t) => { if (statusEl) statusEl.textContent = t }

// Toggle the FreeText (typewriter) tool. NONE = selection/idle, FREETEXT = place text.
let textOn = false
textBtn?.addEventListener('click', () => {
  textOn = !textOn
  textBtn.classList.toggle('on', textOn)
  pdfViewer.annotationEditorMode = {
    mode: textOn ? pdfjsLib.AnnotationEditorType.FREETEXT : pdfjsLib.AnnotationEditorType.NONE,
  }
})

function hasBinding() {
  return !!(bridge && boundSession && pdfDoc)
}

// The plain 💾 Speichern: persist the current PDF.js edits (form values + added FreeText) to
// the bound document AND to disk, via the method that matches HOW the surface was opened: a
// node binding (save_node_back, needs a pdftool binding) vs a directly-opened .pdf 'bridge'
// session (save_pdf_bytes — the bridge open creates NO node binding, so save_node_back rejects
// it). Returns the bridge result.
async function bakeEdits() {
  const b64 = uint8ToBase64(await pdfDoc.saveDocument())
  return sourceMode === 'session'
    ? bridge.save_node_back(boundSession, b64)
    : bridge.save_pdf_bytes(boundSession, b64)
}

// Bake edits into the SESSION ONLY (no disk) before a guarded DATEV op — the on-disk .pdf is
// written by the DATEV op AFTER a successful verdict, so a refused/declined write-back never
// clobbers the local checkout. DATEV is offered for a 'bridge' .pdf only (setupDatevUi), so
// update_pdf_bytes is always the right primitive here.
async function bakeForDatev() {
  const b64 = uint8ToBase64(await pdfDoc.saveDocument())
  return bridge.update_pdf_bytes(boundSession, b64)
}

async function saveBack() {
  if (!hasBinding()) { setStatus('Kein gebundenes Dokument'); return }
  setStatus('Speichern…')
  try {
    const res = await bakeEdits()
    setStatus(res && res.ok ? datevSavedNotice('Gespeichert ✓', res)
      : `Fehler: ${(res && res.error) || 'unbekannt'}`)
  } catch (e) {
    setStatus(`Fehler: ${e}`)
  }
}
saveBtn?.addEventListener('click', saveBack)

// --- DATEV (mode only; this surface opens a DATEV checkout .pdf) -------------
// Bake the current edits into the node first (so the effective bytes DATEV receives reflect
// them), then run the guarded write-back. save_to_datev shows a native confirm before the
// (revision-less, permanent) overwrite. The result names the locally-saved file so the format
// (a plain .pdf for a checkout) is explicit.
async function datevWriteBack() {
  if (!hasBinding()) { setStatus('Kein gebundenes Dokument'); return }
  setStatus('Speichern…')
  try {
    const b64 = uint8ToBase64(await pdfDoc.saveDocument())
    const saved = await bridge.update_pdf_bytes(boundSession, b64)  // session only; disk write after the guard
    if (!saved || !saved.ok) { setStatus(`Fehler: ${(saved && saved.error) || 'unbekannt'}`); return }
    const res = await bridge.save_to_datev(boundSession)
    if (res && res.ok) {
      setStatus(datevSavedNotice('Nach DATEV zurückgeschrieben ✓', res)
        + (res.local_error ? ` — lokal: ${res.local_error}` : ''))
    } else if (res && res.verdict === 'declined') {
      setStatus('Abgebrochen — nicht zurückgeschrieben')
    } else {
      // conflict/locked/error → DATEV refused, but the edit is real work and must not be lost.
      // The bake above was session-only (never touched disk), so persist it to the on-disk .pdf
      // now — mirrors the organizer's saveFile() fallback. The DATEV server copy stays untouched.
      // A guard verdict (locked/conflict_*/no_structure_item) has a localized German message
      // (the four known ones are already prefixed "DATEV: "; an unknown verdict falls back to
      // "DATEV-Rückschreiben fehlgeschlagen."); the 'error' verdict carries the real cause in
      // res.error — show THAT with a "DATEV: " prefix, not the raw code. Mirrors App.jsx.
      const guard = res && res.verdict && res.verdict !== 'error'
      const head = guard ? datevVerdictKey(res.verdict) : `DATEV: ${(res && res.error) || 'fehlgeschlagen'}`
      const local = await bridge.save_pdf_bytes(boundSession, b64)
      // save_pdf_bytes returns ok:true once the session bake succeeds, even if the on-disk
      // write inside _datev_local_persist failed (local_error set). Only claim "lokal gesichert"
      // when the disk write actually landed — otherwise surface the local error so the user
      // never closes the window believing a lost edit is safe.
      setStatus(local && local.ok && !local.local_error
        ? datevSavedNotice(`${head} — lokal gesichert`, local)
        : `${head}${local && local.local_error ? ` — lokal: ${local.local_error}` : ''}`)
    }
  } catch (e) { setStatus(`Fehler: ${e}`) }
}

// Not-connected .pdf → file it as a NEW DATEV document under a prompted Mandant.
async function datevFileNew() {
  if (!hasBinding()) { setStatus('Kein gebundenes Dokument'); return }
  const num = window.prompt('Mandantennummer für die DATEV-Ablage')
  if (!num || !num.trim()) return
  setStatus('Ablegen…')
  try {
    const saved = await bakeForDatev()  // session only; abort if it fails so we never file unedited bytes
    if (!saved || !saved.ok) { setStatus(`Fehler: ${(saved && saved.error) || 'unbekannt'}`); return }
    const res = await bridge.datev_file(boundSession, null, num.trim())
    // On success the parallel local save may still have failed (filed in DATEV but the on-disk
    // .pdf wasn't updated → now stale). Surface res.local_error too, never a bare "✓" — mirrors
    // App.jsx fileToDatev and datevWriteBack's ok-path so the user knows to re-save locally.
    if (res && res.ok) {
      setStatus(datevSavedNotice('In DATEV abgelegt ✓', res)
        + (res.local_error ? ` — lokal: ${res.local_error}` : ''))
    } else setStatus(`DATEV: ${(res && res.error) || 'fehlgeschlagen'}`)
  } catch (e) { setStatus(`Fehler: ${e}`) }
}

// Reveal the DATEV button only for a .pdf opened in DATEV mode ('bridge' source); a write-back
// for a connected checkout, else a file-anew. DATEV mode off (or a node binding) → no DATEV UI.
async function setupDatevUi() {
  if (!datevBtn || !bridge || sourceMode !== 'bridge') return
  let datevMode = false
  try { const st = await bridge.datev_status(); datevMode = !!(st && st.datev_mode) } catch { /* off */ }
  const action = datevAction({ datevMode, connected: datevConnected })
  if (!action) return
  if (action === 'writeback') {
    datevBtn.textContent = '🔗 Nach DATEV zurückschreiben'
    datevBtn.onclick = datevWriteBack
  } else {
    datevBtn.textContent = '📤 Nach DATEV ablegen'
    datevBtn.onclick = datevFileNew
  }
  datevBtn.hidden = false
}

// pywebview injects window.pywebview early and populates .api on 'pywebviewready'.
// A plain browser (dev/e2e) has no window.pywebview → no bridge, no wait.
async function getBridge() {
  if (typeof window.pywebview === 'undefined') return null
  if (window.pywebview.api) return window.pywebview.api
  await new Promise((resolve) => window.addEventListener('pywebviewready', resolve, { once: true }))
  return window.pywebview.api || null
}

async function resolveDocumentArgs() {
  const fileParam = new URLSearchParams(location.search).get('file')
  const urlFallback = fileParam || '/spike-form.pdf'
  const api = await getBridge()
  bridge = api
  const cfg = api ? await api.config() : null
  const src = chooseSource({ hasBridge: !!api, cfg, fileParam })
  sourceMode = src.mode
  if (src.mode === 'session') {
    // node binding: the host already opened the bound session; just fetch its bytes
    boundSession = src.session
    const res = await api.get_pdf_bytes(src.session)
    if (res?.ok) return { data: base64ToUint8(res.data_b64) }
  } else if (src.mode === 'bridge') {
    const opened = await api.open(null, src.path)
    if (opened?.ok) {
      boundSession = opened.session
      // a DATEV checkout path captures provenance on open → the open response flags it
      datevConnected = !!(opened.datev && opened.datev.connected)
      const res = await api.get_pdf_bytes(opened.session)
      if (res?.ok) return { data: base64ToUint8(res.data_b64) }
    }
    // bridge open/fetch failed → fall back to a URL rather than a blank window
  }
  return { url: urlFallback }
}

resolveDocumentArgs()
  .then((args) => pdfjsLib.getDocument(args).promise)
  .then((pdfDocument) => {
    pdfDoc = pdfDocument
    linkService.setDocument(pdfDocument, null)
    pdfViewer.setDocument(pdfDocument)
    window.__viewerDocReady = true
    // Save only makes sense when bound to a node/file in the host (not the URL sample).
    if (saveBtn) saveBtn.disabled = !(bridge && boundSession)
    setupDatevUi()  // reveal the DATEV action for a checkout .pdf opened in DATEV mode
  })
  .catch((err) => {
    window.__viewerError = String(err)
    console.error('pdf-tool load failed', err)
  })
