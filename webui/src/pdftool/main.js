// PDF-Tool surface (step 2 of the two-surface design; see docs/pdf-tool.md).
// Renders the BOUND PDF: in the pywebview host it pulls the bound .pdf's bytes over
// the bridge (get_pdf_bytes); in a plain browser (dev/e2e) it loads a URL sample.
// Mozilla's reference viewer components give the selectable text layer + AcroForm.
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { EventBus, PDFViewer, PDFLinkService } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'
import { chooseSource, base64ToUint8 } from './source.js'

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl

const container = document.getElementById('viewerContainer')
const eventBus = new EventBus()
const linkService = new PDFLinkService({ eventBus })
const pdfViewer = new PDFViewer({
  container,
  eventBus,
  linkService,
  // ENABLE_FORMS renders AcroForm widgets as interactive HTML inputs.
  annotationMode: pdfjsLib.AnnotationMode.ENABLE_FORMS,
})
linkService.setViewer(pdfViewer)

// Signal flags the e2e spec waits on (cheaper than guessing timings).
eventBus.on('textlayerrendered', () => { window.__viewerTextLayerReady = true })
eventBus.on('annotationlayerrendered', () => { window.__viewerFormLayerReady = true })

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
  const cfg = api ? await api.config() : null
  const src = chooseSource({ hasBridge: !!api, cfg, fileParam })
  if (src.mode === 'bridge') {
    const opened = await api.open(null, src.path)
    if (opened?.ok) {
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
    linkService.setDocument(pdfDocument, null)
    pdfViewer.setDocument(pdfDocument)
    window.__viewerDocReady = true
  })
  .catch((err) => {
    window.__viewerError = String(err)
    console.error('pdf-tool load failed', err)
  })
