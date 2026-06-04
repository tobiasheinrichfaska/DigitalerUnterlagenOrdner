// Thin wrapper over the pywebview-injected core API (window.pywebview.api).
// pywebview attaches the API after the window loads (the `pywebviewready` event),
// so every call waits for it first. In a plain browser (no host) calls reject.

const apiObj = () => (window.pywebview && window.pywebview.api) || null

function waitForApi() {
  return new Promise((resolve, reject) => {
    if (apiObj()) return resolve(apiObj())
    window.addEventListener('pywebviewready', () => resolve(apiObj()), { once: true })
    // Fail fast if we're not running inside the host (e.g. opened in a browser).
    setTimeout(() => {
      if (!apiObj()) reject(new Error('core API not available (not running in the host)'))
    }, 4000)
  })
}

// A runtime-created (2nd) window can expose `window.pywebview.api` a beat BEFORE its
// methods are bound, so a startup call would hit "api[method] is not a function".
// Wait until THIS method is actually callable, not just until `api` exists.
async function resolveMethod(method) {
  let api = await waitForApi()
  for (let i = 0; i < 100 && !(api && typeof api[method] === 'function'); i++) {
    await new Promise((r) => setTimeout(r, 50))
    api = apiObj() || api
  }
  if (!api || typeof api[method] !== 'function') {
    throw new Error(`core API method not available: ${method}`)
  }
  return api
}

// --- background-activity tracking (for the status bar) ---------------------
// Compression is counted by DISTINCT NODE (not per call): selecting one node fires
// both compress_options AND render_compressed_window, so a per-call count would read
// "2" for one node. Rendering is a simple in-flight count.
const compressing = new Map() // nodeId -> in-flight compress calls
let renderInflight = 0
const activityListeners = new Set()
const snapshot = () => ({ compress: compressing.size, render: renderInflight })
const notifyActivity = () => { const s = snapshot(); activityListeners.forEach((l) => l(s)) }

export function onActivity(fn) {
  activityListeners.add(fn)
  fn(snapshot())
  return () => activityListeners.delete(fn)
}

function categoryOf(method) {
  if (method === 'compress_options' || method === 'render_compressed_window') return 'compress'
  if (method === 'render_window' || method === 'render' || method === 'render_compressed') return 'render'
  return null // metadata / IO calls aren't shown as background activity
}

async function call(method, ...args) {
  const api = await resolveMethod(method)
  const cat = categoryOf(method)
  const nodeId = args[1] // tracked calls are (session, nodeId, …)
  if (cat === 'compress') { compressing.set(nodeId, (compressing.get(nodeId) || 0) + 1); notifyActivity() }
  else if (cat === 'render') { renderInflight += 1; notifyActivity() }
  try {
    return await api[method](...args)
  } finally {
    if (cat === 'compress') {
      const c = (compressing.get(nodeId) || 1) - 1
      if (c <= 0) compressing.delete(nodeId); else compressing.set(nodeId, c)
      notifyActivity()
    } else if (cat === 'render') { renderInflight -= 1; notifyActivity() }
  }
}

export const core = {
  config: () => call('config'),
  newWindow: () => call('new_window'),
  setDirty: (value) => call('set_dirty', value),
  open: (session = null, path = null) => call('open', session, path),
  openFile: (session = null) => call('open_file', session),
  saveFile: (session) => call('save_file', session),
  saveFileAs: (session) => call('save_file_as', session),
  dispatch: (session, command) => call('dispatch', session, command),
  undo: (session) => call('undo', session),
  redo: (session) => call('redo', session),
  render: (session, nodeId) => call('render', session, nodeId),
  renderCompressed: (session, nodeId, dpi, method) => call('render_compressed', session, nodeId, dpi, method),
  compressOptions: (session, nodeId, dpi) => call('compress_options', session, nodeId, dpi),
  testMode: (dpi = 72, maxPages = 12) => call('test_mode', dpi, maxPages),
  pageCount: (session, nodeId) => call('page_count', session, nodeId),
  pageDims: (session, nodeId) => call('page_dims', session, nodeId),
  renderStats: () => call('render_stats'),
  setCacheBudget: (mb) => call('set_render_budget', mb),
  renderWindow: (session, nodeId, first = 0, count = 10, dpi = 100) =>
    call('render_window', session, nodeId, first, count, dpi),
  renderCompressedWindow: (session, nodeId, dpi, method, first = 0, count = 10) =>
    call('render_compressed_window', session, nodeId, dpi, method, first, count),
  exportPdf: (session, nodeIds = null) => call('export_dialog', session, nodeIds),
  importDialog: (session, parentId = null) => call('import_dialog', session, parentId),
  importBytes: (session, name, data, parentId = null, index = null) => call('import_bytes', session, name, data, parentId, index),
}
