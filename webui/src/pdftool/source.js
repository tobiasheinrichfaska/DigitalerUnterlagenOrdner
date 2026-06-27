// Pure helpers for the PDF-Tool surface's source selection — UI-free, unit-tested.
// (See docs/pdf-tool.md: the surface renders the bytes of whatever it is bound to.)

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
//  - 'writeback' when the open .pdf is a DATEV checkout (connected) → guarded write-back;
//  - 'file' when DATEV mode is on but the document is NOT connected → file it as a new doc;
//  - null when DATEV mode is off (no DATEV UI at all).
export function datevAction({ datevMode, connected }) {
  if (!datevMode) return null
  return connected ? 'writeback' : 'file'
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
