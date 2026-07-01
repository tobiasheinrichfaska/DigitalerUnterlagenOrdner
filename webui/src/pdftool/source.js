// Pure helpers for the PDF-Tool surface's source selection — UI-free, unit-tested.
// (See docs/pdf-tool.md: the surface renders the bytes of whatever it is bound to.)

// The host bridge is usable only when window.pywebview.api exists AND every method
// the surface needs is actually bound. The PDF-Tool is ALWAYS a runtime-created (2nd)
// window, where pywebview can expose .api a beat BEFORE its methods bind — gating on
// the object alone would hand back a half-built api and the first call would throw.
// Returns the api or null. Pure + unit-tested (the spike-form bug was the missing
// method-binding wait here).
export function readyBridge(win, methods) {
  const api = (win && win.pywebview && win.pywebview.api) || null
  if (!api) return null
  return methods.every((m) => typeof api[m] === 'function') ? api : null
}

// Decide where the PDF bytes come from. In the host with a bound .pdf, fetch the
// bytes over the bridge; otherwise (dev / browser / e2e, or no bound pdf) load a URL.
export function chooseSource({ hasBridge, cfg, fileParam }) {
  if (hasBridge && cfg) {
    // a node opens a PRE-BOUND pdf-tool session (no file path) — fetch its bytes directly
    if (cfg.startup_kind === 'node' && cfg.startup_session) {
      return { mode: 'session', session: cfg.startup_session }
    }
    // a .pdf opens bound to the file — open it, then fetch its bytes
    if (cfg.startup_kind === 'pdf' && cfg.startup_path) {
      return { mode: 'bridge', path: cfg.startup_path }
    }
  }
  return { mode: 'url', url: fileParam || '/spike-form.pdf' }
}

// Which DATEV action the PDF-Tool offers for the open document (DATEV mode only):
//  - 'writeback' when the open .pdf is a connected checkout that is NOT checked out → guarded
//    in-place API write-back;
//  - 'file' when DATEV mode is on but the document is NOT connected → file it as a new doc;
//  - null when DATEV mode is off, OR the doc is connected AND CHECKED OUT. DATEV refuses an API
//    write-back on a checked-out document, so no write-back button is shown — the user saves the
//    local working copy with 💾 Speichern and checks it in via DATEV (the native DokOrg flow).
export function datevAction({ datevMode, connected, checkedOut }) {
  if (!datevMode) return null
  if (connected) return checkedOut ? null : 'writeback'
  return 'file'
}

// base64 → Uint8Array for PDF.js getDocument({ data }).
export function base64ToUint8(b64) {
  const bin = atob(b64)
  const arr = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) arr[i] = bin.charCodeAt(i)
  return arr
}

// Uint8Array → base64 for the save-back bridge call (PDF.js saveDocument() output).
// Chunked so a multi-MB PDF doesn't blow String.fromCharCode's argument limit.
export function uint8ToBase64(bytes) {
  const CHUNK = 0x8000
  let bin = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK))
  }
  return btoa(bin)
}
