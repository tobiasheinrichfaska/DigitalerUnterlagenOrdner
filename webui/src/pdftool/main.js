// SPIKE — PDF-Tool surface (step 1 of the two-surface design;
// see docs/pdf-tool.md). Proves, inside this app's WebView2/Chromium,
// that we get: (1) a selectable TEXT layer and (2) interactive AcroForm fields,
// using Mozilla's reference viewer components (pdfjs-dist/web/pdf_viewer.mjs).
//
// This is throwaway plumbing: it loads a static sample PDF by ?file= (default
// /spike-form.pdf). Step 2 replaces the URL load with bytes from CoreApi and
// adds the binding/persistence model (bind-to-pdf / bind-to-node).
import * as pdfjsLib from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { EventBus, PDFViewer, PDFLinkService } from 'pdfjs-dist/web/pdf_viewer.mjs'
import 'pdfjs-dist/web/pdf_viewer.css'

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

const file = new URLSearchParams(location.search).get('file') || '/spike-form.pdf'
pdfjsLib.getDocument({ url: file }).promise
  .then((pdfDocument) => {
    linkService.setDocument(pdfDocument, null)
    pdfViewer.setDocument(pdfDocument)
    window.__viewerDocReady = true
  })
  .catch((err) => {
    window.__viewerError = String(err)
    console.error('pdf-tool spike load failed', err)
  })
