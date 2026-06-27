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
import { chooseSource, base64ToUint8, uint8ToBase64 } from './source.js'

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

const textBtn = document.getElementById('btn-text')
const saveBtn = document.getElementById('btn-save')
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

async function saveBack() {
  if (!bridge || !boundSession || !pdfDoc) { setStatus('Kein gebundenes Dokument'); return }
  setStatus('Speichern…')
  try {
    const bytes = await pdfDoc.saveDocument()  // form values + added FreeText baked in
    const res = await bridge.save_node_back(boundSession, uint8ToBase64(bytes))
    setStatus(res && res.ok ? 'Gespeichert ✓' : `Fehler: ${(res && res.error) || 'unbekannt'}`)
  } catch (e) {
    setStatus(`Fehler: ${e}`)
  }
}
saveBtn?.addEventListener('click', saveBack)

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
  if (src.mode === 'session') {
    // node binding: the host already opened the bound session; just fetch its bytes
    boundSession = src.session
    const res = await api.get_pdf_bytes(src.session)
    if (res?.ok) return { data: base64ToUint8(res.data_b64) }
  } else if (src.mode === 'bridge') {
    const opened = await api.open(null, src.path)
    if (opened?.ok) {
      boundSession = opened.session
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
  })
  .catch((err) => {
    window.__viewerError = String(err)
    console.error('pdf-tool load failed', err)
  })
