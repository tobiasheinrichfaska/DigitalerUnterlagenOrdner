// PDF-Tool surface (see docs/pdf-tool.md). Renders the BOUND PDF and lets the user
// add text (FreeText / typewriter) and fill forms, then save it back into the node:
//   PDF.js saveDocument() bakes the additions in as real FreeText annotations + form
//   values → bytes → bridge.save_node_back(session, b64) → SetNodeBytes on the node.
// Self-authored text round-trips: reopening the node loads the annotations back into
// the editor as editable objects (PDF.js re-loads its own annotations).
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { EventBus, PDFViewer, PDFLinkService, LinkTarget } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'
import { chooseSource, readyBridge, base64ToUint8, uint8ToBase64, datevAction, saveFailure } from './source.js'
import { openFileDialog } from './fileDialog.js'
import { datevSavedNotice, datevVerdictKey } from '../lib/datev.js'
import { installDropGuard } from '../lib/dropGuard.js'
import { openPasswordDialog } from './passwordDialog.js'
import { toolT } from './lang.js'

// A file/link dropped on this window must never navigate it: pywebview would re-inject the JS
// bridge into the dropped page (security review 2026-11-25, H-3).
installDropGuard(window)

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

// PDF.js v6 fetches its image decoders (wasm) + cmap/standard-font data at render time. DATEV
// documents are SCANS (JBIG2 / JPEG2000), which decode via wasm/jbig2.wasm + wasm/openjpeg.wasm
// — without these served the page count is correct but every page renders BLANK. The vite
// `pdfjsAssets` plugin serves them at /pdfjs/* (dev) and copies them into the build (prod);
// absolute URLs (resolved against baseURI) so the PDF.js worker can fetch them too.
const PDFJS_ASSET_BASE = new URL('pdfjs/', document.baseURI).href
const PDFJS_ASSET_OPTS = {
  cMapUrl: `${PDFJS_ASSET_BASE}cmaps/`,
  cMapPacked: true,
  standardFontDataUrl: `${PDFJS_ASSET_BASE}standard_fonts/`,
  wasmUrl: `${PDFJS_ASSET_BASE}wasm/`,
  iccUrl: `${PDFJS_ASSET_BASE}iccs/`,
}

const container = document.getElementById('viewerContainer')
const eventBus = new EventBus()
// externalLinkTarget=BLANK: a link in an untrusted PDF must never navigate THIS
// window — pywebview re-injects the full JS bridge into whatever loads here, so a
// same-window navigation would hand window.pywebview.api to a remote page (and
// even a benign link would discard unsaved edits). target=_blank is routed by
// pywebview to the SYSTEM browser. Guarded by e2e "PDF-Tool external links".
const linkService = new PDFLinkService({ eventBus, externalLinkTarget: LinkTarget.BLANK })
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
let sourceMode = null        // 'session' | 'bridge' | 'url' — DATEV UI for a 'bridge' .pdf or a 'session' node
let datevConnected = false   // the open .pdf is a DATEV checkout (provenance from its path)
let datevCheckedOut = false  // the DATEV doc is checked out at open → no API write-back (use Speichern)
let datevSourceName = ''     // the linked DATEV source file name (for the "verknüpft" badge)
let suggestedName = ''       // default Bezeichnung for the filing dialog (the source file name)

const textBtn = document.getElementById('btn-text')
const saveBtn = document.getElementById('btn-save')
const datevBtn = document.getElementById('btn-datev')
const statusEl = document.getElementById('pdf-status')
// status text is ellipsized in the toolbar (so long errors don't squash the buttons) →
// mirror the full text into the tooltip so the user can still read all of it on hover.
const setStatus = (t) => { if (statusEl) { statusEl.textContent = t; statusEl.title = t || '' } }

// Toggle the FreeText (typewriter) tool. NONE = selection/idle, FREETEXT = place text.
let textOn = false
textBtn?.addEventListener('click', () => {
  textOn = !textOn
  textBtn.classList.toggle('on', textOn)
  pdfViewer.annotationEditorMode = {
    mode: textOn ? pdfjsLib.AnnotationEditorType.FREETEXT : pdfjsLib.AnnotationEditorType.NONE,
  }
})

// Unsaved-edit tracking (PT-2): PDF.js flags its annotationStorage as modified on every added /
// changed / removed FreeText and every changed form value. The state is pushed to the host
// (HostApi.set_dirty → the window close guard asks before discarding) and mirrored on
// window.__belegDirty like the organizer.
//
// R11-3 (2026-11-28): dirty is derived from OUR OWN state, never from PDF.js' reset signal
// (saveDocument() resets the storage itself BEFORE the bridge write, so a failed save used to
// look clean). dirty = (hash of annotationStorage.serializable) != baseline, where the baseline
// is the load-time snapshot (re-taken on every layer render until the user first touches a
// widget/editor → PDF.js' own setValue calls while rendering radio widgets never count) and,
// after a save, exactly the bytes' snapshot — set only once the bridge reported success.
let dirty = false
let saving = false
let editVersion = 0          // ++ on every onSetModified
let baseline = null          // storage snapshot considered "saved"; null until first render
let userTouched = false      // the user edited something (input/change/key/pointer on a widget)
window.__belegDirty = false
function setDirty(v) {
  if (dirty === v) return
  dirty = v
  window.__belegDirty = v
  if (saveBtn) saveBtn.classList.toggle('dirty', v)
  try { Promise.resolve(bridge && bridge.set_dirty && bridge.set_dirty(v)).catch(() => {}) } catch { /* ignore */ }
}
function storageHash() {
  try { return pdfDoc.annotationStorage.serializable.hash || '' } catch { return `v${editVersion}` }
}
function refreshDirty() { if (baseline !== null) setDirty(storageHash() !== baseline) }
function onStorageModified() {
  editVersion += 1
  if (!userTouched) {
    // Render artefact (radio widgets call setValue while rendering): not an edit. Re-baseline and
    // re-arm PDF.js' modified flag so the user's first REAL edit raises the event again.
    baseline = storageHash()
    try { pdfDoc.annotationStorage.resetModified() } catch { /* ignore */ }
    return
  }
  refreshDirty()
}
// Capture what a bake is about to serialize (call synchronously before saveDocument()).
const bakeToken = () => ({ v: editVersion, h: storageHash() })
// Mark saved ONLY after the bridge confirmed; an edit made while the save was in flight stays dirty.
function markSaved(tok) {
  baseline = tok.h
  if (editVersion !== tok.v || storageHash() !== tok.h) setDirty(true)
  else setDirty(false)
}
// R12-5: only REAL edit interactions arm userTouched: events targeting a form widget / an editor-layer
// element. Navigation keys (PageDown/arrows/Tab on the page) and scrolling never count.
const EDIT_TARGET = '.annotationLayer, .annotationEditorLayer, .freeTextEditor, [data-annotation-id], [contenteditable]'
const inEditTarget = (e) => !!(e.target && e.target.closest && e.target.closest(EDIT_TARGET))
const touch = (e) => { if (inEditTarget(e)) userTouched = true }
document.addEventListener('input', touch, true)
document.addEventListener('change', touch, true)
document.addEventListener('keydown', touch, true)
document.addEventListener('pointerdown', (e) => { if (inEditTarget(e) || textOn) userTouched = true }, true)
eventBus.on('annotationlayerrendered', () => { if (pdfDoc && !userTouched) baseline = storageHash() })

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
  if (saving) return  // PT-7: no concurrent saves
  if (!hasBinding()) { setStatus('Kein gebundenes Dokument'); return }
  // PT-4: nothing edited → nothing to write (a save would replace the node's source and reset
  // its compression decision for byte-identical content).
  if (!dirty) { setStatus(toolT('Keine Änderungen zu speichern.')); return }
  saving = true
  saveBtn.disabled = true
  setStatus('Speichern…')
  try {
    const tok = bakeToken()
    const res = await bakeEdits()
    const fail = saveFailure(res)
    if (fail === null) markSaved(tok)
    setStatus(fail === null ? datevSavedNotice('Gespeichert ✓', res) : `Fehler: ${fail}`)
  } catch (e) {
    setStatus(`Fehler: ${e}`)
  } finally {
    saving = false
    saveBtn.disabled = !hasBinding()
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
    const tok = bakeToken()
    const b64 = uint8ToBase64(await pdfDoc.saveDocument())
    const saved = await bridge.update_pdf_bytes(boundSession, b64)  // session only; disk write after the guard
    if (!saved || !saved.ok) { setStatus(`Fehler: ${(saved && saved.error) || 'unbekannt'}`); return }
    const res = await bridge.save_to_datev(boundSession)
    if (res && res.ok) {
      // checked_out_self = the doc is checked out by ME → DATEV won't take an API write-back, so we
      // saved the local working copy; the user checks it in via DATEV. Say exactly that.
      const msg = res.verdict === 'checked_out_self'
        ? '📥 In die ausgecheckte Datei gespeichert — bitte in DATEV einchecken'
        : 'Nach DATEV zurückgeschrieben ✓'
      if (!res.local_error) markSaved(tok)
      setStatus(datevSavedNotice(msg, res) + (res.local_error ? ` — lokal: ${res.local_error}` : ''))
    } else if (res && res.verdict === 'checked_out_self') {
      // checked out by me, but the local working copy could not be written (locked) → nothing more
      // we can do (DATEV refuses the API write while checked out); surface it, don't re-try locally.
      setStatus('DATEV: Ausgecheckte Datei konnte nicht gespeichert werden (gesperrt?)'
        + (res.local_error ? ` — ${res.local_error}` : ''))
    } else if (res && res.verdict === 'declined') {
      // "Nein" = only update the local checked-out file (no DATEV push); the bake was session-only
      // so persist the edited .pdf to disk now. The user checks it in via DATEV later.
      const local = await bridge.save_pdf_bytes(boundSession, b64)
      if (local && local.ok && !local.local_error) markSaved(tok)
      setStatus(local && local.ok && !local.local_error
        ? datevSavedNotice('Nur lokal gespeichert (nicht in DATEV)', local)
        : `Fehler beim lokalen Speichern: ${(local && local.local_error) || 'unbekannt'}`)
    } else {
      // conflict/locked/error → DATEV refused, but the edit is real work and must not be lost.
      // The bake above was session-only (never touched disk), so persist it to the on-disk .pdf
      // now — mirrors the organizer's saveFile() fallback. The DATEV server copy stays untouched.
      // A guard verdict (locked/conflict_*/no_structure_item) has a localized German message
      // (the four known ones are already prefixed "DATEV: "; an unknown verdict falls back to
      // "DATEV-Rückschreiben fehlgeschlagen."); the 'error' verdict carries the real cause in
      // res.error — show THAT with a "DATEV: " prefix, not the raw code. Mirrors App.jsx.
      const guard = res && res.verdict && res.verdict !== 'error'
      const who = res && res.checkout_by ? ` (${res.checkout_by})` : ''  // locked → WHO has it
      const head = (guard ? datevVerdictKey(res.verdict) : `DATEV: ${(res && res.error) || 'fehlgeschlagen'}`) + who
      const local = await bridge.save_pdf_bytes(boundSession, b64)
      if (local && local.ok && !local.local_error) markSaved(tok)
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

// Not-connected .pdf → file it as a NEW DATEV document. Opens the same filing dialog as the
// organizer (searchable Mandant + folder/register + Belegdatum + Veranlagung year/month). No
// client data ⇒ filing is refused (the user's rule) rather than a blind prompt.
async function datevFileNew() {
  if (!hasBinding()) { setStatus('Kein gebundenes Dokument'); return }
  setStatus('Mandanten werden geladen…')
  let clientsRes, placeRes
  try {
    [clientsRes, placeRes] = await Promise.all([bridge.datev_clients(), bridge.datev_placements()])
  } catch (e) { setStatus(`Fehler: ${e}`); return }
  if (!clientsRes || !clientsRes.ok) {
    setStatus(`DATEV: ${(clientsRes && clientsRes.error) || 'Mandantenliste nicht verfügbar'}`); return
  }
  const clients = clientsRes.clients || []
  if (!clients.length) { setStatus('Keine Mandanten gefunden — DATEV-Ablage nicht möglich.'); return }
  const opts = await openFileDialog({ clients,
    placements: (placeRes && placeRes.ok && placeRes.folders) || [],
    currentYear: new Date().getFullYear(), defaultName: suggestedName })
  if (!opts) { setStatus(''); return }  // cancelled
  setStatus('Ablegen…')
  try {
    const tok = bakeToken()
    const saved = await bakeForDatev()  // session only; abort if it fails so we never file unedited bytes
    if (!saved || !saved.ok) { setStatus(`Fehler: ${(saved && saved.error) || 'unbekannt'}`); return }
    const res = await bridge.datev_file(boundSession, opts.clientGuid, null, opts.description ?? null, 1,
      opts.folderId ?? null, opts.registerId ?? null, opts.documentDate ?? null,
      opts.fiscalYear ?? null, opts.fiscalMonth ?? null)
    // On success the parallel local save may still have failed (filed in DATEV but the on-disk
    // .pdf wasn't updated → now stale). Surface res.local_error too, never a bare "✓" — mirrors
    // App.jsx fileToDatev and datevWriteBack's ok-path so the user knows to re-save locally.
    if (res && res.ok) {
      if (!res.local_error) markSaved(tok)
      setStatus(datevSavedNotice('In DATEV abgelegt ✓', res)
        + (res.local_error ? ` — lokal: ${res.local_error}` : ''))
    } else setStatus(`DATEV: ${(res && res.error) || 'fehlgeschlagen'}`)
  } catch (e) { setStatus(`Fehler: ${e}`) }
}

// Reveal the DATEV button for a PDF opened in DATEV mode — either a directly-opened .pdf
// ('bridge') or a node opened "in PDF-Tool" ('session'). A connected checkout (.pdf only)
// offers write-back; everything else offers file-anew. A node binding is never "connected"
// (the organizer owns any DATEV link), so it always offers file-anew. DATEV mode off → no UI.
async function setupDatevUi() {
  if (!datevBtn || !bridge || (sourceMode !== 'bridge' && sourceMode !== 'session')) return
  let datevMode = false
  let st = null
  try { st = await bridge.datev_status(); datevMode = !!(st && st.datev_mode) } catch { /* off */ }
  if (!datevMode) return
  // action: 'writeback' (connected + NOT checked out), 'file' (not connected), or null (connected
  // AND checked out → no API write-back; the user updates the working copy with 💾 Speichern and
  // checks it in via DATEV). DATEV mode off already returned above.
  const action = datevAction({ datevMode, connected: datevConnected, checkedOut: datevCheckedOut })
  if (action === 'writeback') {
    datevBtn.textContent = '🔗 Nach DATEV zurückschreiben'
    datevBtn.onclick = datevWriteBack
    datevBtn.hidden = false
  } else if (action === 'file') {
    datevBtn.textContent = '📤 Nach DATEV ablegen'
    datevBtn.onclick = datevFileNew
    datevBtn.hidden = false
  } else {
    datevBtn.hidden = true   // connected + checked out → no write-back button (use 💾 Speichern)
  }
  // A persistent "linked to DATEV" badge (a connected checkout) — the user could not tell a
  // checkout was DATEV-linked from the action button alone. When checked out, the badge also says
  // HOW to save (Speichern → check in via DATEV), since there is no write-back button.
  const linkEl = document.getElementById('datev-link')
  if (linkEl && datevConnected) {
    const co = datevCheckedOut ? ' · ausgecheckt (💾 Speichern → in DATEV einchecken)' : ''
    linkEl.textContent = `🔗 Mit DATEV verknüpft${datevSourceName ? ` · ${datevSourceName}` : ''}${co}`
    linkEl.title = linkEl.textContent   // full text on hover when ellipsised
    linkEl.hidden = false
  }
  if (datevBtn.hidden) return   // no action button → no connection polling needed
  // Never offer a DATEV write without a connection — disable + explain instead of a dead click.
  // The connect runs in the background (slow SSO), so while it is still in flight (connecting)
  // re-poll ~every 1.5s and re-enable once it settles, mirroring the organizer (App.jsx) — a
  // single read would otherwise latch the button disabled even after the connect succeeds.
  const applyConn = (status) => {
    const connected = !!(status && status.connected)
    datevBtn.disabled = !connected
    datevBtn.title = connected ? '' : (status && status.connecting
      ? 'Verbindung zur DATEV-Schnittstelle…' : 'Keine Verbindung zur DATEV-Schnittstelle')
    if (!connected && status && status.connecting) {
      // Promise.resolve so a sync bridge return (tests) works as well as the real async bridge.
      setTimeout(() => Promise.resolve(bridge.datev_status()).then(applyConn).catch(() => {}), 1500)
    }
  }
  applyConn(st)
}

// The bridge methods the surface needs to LOAD a bound document. The PDF-Tool is
// ALWAYS a runtime-created (2nd) window, where pywebview can expose window.pywebview
// — and even .api — a beat BEFORE the methods are actually bound (the exact race
// lib/core.js guards for the organizer). The old getBridge() bailed to null the
// instant window.pywebview was missing, so a fresh window lost the bridge and fell
// through to the dev sample PDF (the "SPIKE" form) for BOTH node and .pdf opens.
const BRIDGE_METHODS = ['config', 'get_pdf_bytes', 'open']

// The live api iff window.pywebview.api exists AND every method we need is bound.
const bridgeReady = () => readyBridge(window, BRIDGE_METHODS)

// Resolve the host bridge, waiting out the 2nd-window injection race. Fast path:
// the 'pywebviewready' event. Safety net: poll until the methods bind. After the
// timeout with still no host (a plain browser / e2e) → null, so the surface loads a
// sample/URL document instead of hanging. Matches lib/core.js's 4 s budget.
async function getBridge(timeoutMs = 4000) {
  const ready = bridgeReady()
  if (ready) return ready
  return new Promise((resolve) => {
    const t0 = Date.now()
    const tick = () => {
      const api = bridgeReady()
      if (api) return resolve(api)
      if (Date.now() - t0 >= timeoutMs) return resolve(null)  // no host → sample URL
      setTimeout(tick, 50)
    }
    window.addEventListener('pywebviewready', tick, { once: true })
    tick()
  })
}

async function resolveDocumentArgs() {
  // ?file= is a dev/e2e convenience only — in a production build the page can be navigated
  // (or linked) with a query string, and must not then load an arbitrary URL as its document.
  const fileParam = import.meta.env.DEV ? new URLSearchParams(location.search).get('file') : null
  const urlFallback = fileParam || '/spike-form.pdf'
  const api = await getBridge()
  bridge = api
  // No host at all (plain browser / e2e / dev) → load the sample or ?file= URL.
  if (!api) { sourceMode = 'url'; return { url: urlFallback } }
  const cfg = await api.config()
  const src = chooseSource({ hasBridge: true, cfg, fileParam })
  sourceMode = src.mode
  // In the host a PDF-Tool window is ALWAYS bound (node or .pdf). If the bridge call
  // fails we surface the REAL reason instead of silently rendering the dev sample —
  // a fake document the user can't tell from their own. The sample only ever shows
  // with no host or an explicit ?file= override (src.mode === 'url').
  if (src.mode === 'session') {
    boundSession = src.session
    const res = await api.get_pdf_bytes(src.session)
    if (res?.ok) return { data: base64ToUint8(res.data_b64) }
    throw new Error(`Dokument konnte nicht geladen werden: ${(res && res.error) || 'unbekannt'}`)
  }
  if (src.mode === 'bridge') {
    const opened = await api.open(null, src.path)
    if (!opened?.ok) {
      throw new Error(`Öffnen fehlgeschlagen: ${(opened && opened.error) || 'unbekannt'}`)
    }
    boundSession = opened.session
    // default Bezeichnung for a file-anew = the source file's name (without the .pdf extension)
    suggestedName = String(src.path).split(/[\\/]/).pop().replace(/\.pdf$/i, '')
    // a DATEV checkout path captures provenance on open → the open response flags it
    datevConnected = !!(opened.datev && opened.datev.connected)
    datevCheckedOut = !!(opened.datev && opened.datev.checked_out_at_open)
    datevSourceName = (opened.datev && opened.datev.source_name) || ''
    const res = await api.get_pdf_bytes(opened.session)
    if (res?.ok) return { data: base64ToUint8(res.data_b64) }
    throw new Error(`Dokument konnte nicht geladen werden: ${(res && res.error) || 'unbekannt'}`)
  }
  return { url: urlFallback }  // host present but nothing bound (shouldn't happen)
}

// PT-1: an encrypted PDF asks for its password. The password only flows dialog → PDF.js
// updatePassword; it is never logged or stored. Cancel aborts the load with a clear message.
class PasswordCancelled extends Error {}
function loadDocument(args) {
  const task = pdfjsLib.getDocument({ ...args, ...PDFJS_ASSET_OPTS })
  const cancelled = new Promise((_, reject) => {
    task.onPassword = async (updatePassword, reason) => {
      const pw = await openPasswordDialog({ wrong: reason === pdfjsLib.PasswordResponses.INCORRECT_PASSWORD })
      if (pw === null) {
        reject(new PasswordCancelled(toolT('Passwort-Eingabe abgebrochen – das Dokument wurde nicht geöffnet.')))
        try { task.destroy() } catch { /* ignore */ }
        return
      }
      updatePassword(pw)
    }
  })
  return Promise.race([task.promise, cancelled])
}

resolveDocumentArgs()
  .then(loadDocument)
  .then((pdfDocument) => {
    pdfDoc = pdfDocument
    pdfDocument.annotationStorage.onSetModified = onStorageModified
    // onResetModified is deliberately ignored (R11-3): PDF.js resets BEFORE the bridge write.
    baseline = ''  // empty storage until the first layer render re-baselines
    linkService.setDocument(pdfDocument, null)
    pdfViewer.setDocument(pdfDocument)
    window.__viewerDocReady = true
    // Save only makes sense when bound to a node/file in the host (not the URL sample).
    if (saveBtn) saveBtn.disabled = !(bridge && boundSession)
    setupDatevUi()  // reveal the DATEV action for a checkout .pdf opened in DATEV mode
  })
  .catch((err) => {
    window.__viewerError = String(err)
    if (textBtn) textBtn.disabled = true  // PT-7: nothing to edit after a failed load
    console.error('pdf-tool load failed', err)
    // Show the real reason in the status bar instead of a blank window.
    setStatus(`Fehler: ${(err && err.message) || err}`)
  })
