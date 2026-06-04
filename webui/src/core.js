// Thin wrapper over the pywebview-injected core API (window.pywebview.api).
// pywebview attaches the API after the window loads (the `pywebviewready` event),
// so every call waits for it first. In a plain browser (no host) calls reject.

function waitForApi() {
  return new Promise((resolve, reject) => {
    if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api)
    window.addEventListener(
      'pywebviewready',
      () => resolve(window.pywebview.api),
      { once: true },
    )
    // Fail fast if we're not running inside the host (e.g. opened in a browser).
    setTimeout(() => {
      if (!(window.pywebview && window.pywebview.api)) reject(new Error('core API not available (not running in the host)'))
    }, 4000)
  })
}

// --- background-activity tracking (for the status bar) ---------------------
// Count in-flight heavy calls per category so the UI can show what's running.
const activity = { compress: 0, render: 0 }
const activityListeners = new Set()
const notifyActivity = () => { const s = { ...activity }; activityListeners.forEach((l) => l(s)) }

export function onActivity(fn) {
  activityListeners.add(fn)
  fn({ ...activity })
  return () => activityListeners.delete(fn)
}

function categoryOf(method) {
  if (method === 'compress_options' || method === 'render_compressed_window') return 'compress'
  if (method === 'render_window' || method === 'render' || method === 'render_compressed') return 'render'
  return null // metadata / IO calls aren't shown as background activity
}

async function call(method, ...args) {
  const api = await waitForApi()
  const cat = categoryOf(method)
  if (cat) { activity[cat] += 1; notifyActivity() }
  try {
    return await api[method](...args)
  } finally {
    if (cat) { activity[cat] -= 1; notifyActivity() }
  }
}

export const core = {
  config: () => call('config'),
  newWindow: () => call('new_window'),
  setDirty: (value) => call('set_dirty', value),
  open: (session = null, path = null) => call('open', session, path),
  openFile: (session = null) => call('open_file', session),
  saveFile: (session) => call('save_file', session),
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
  renderWindow: (session, nodeId, first = 0, count = 10, dpi = 100) =>
    call('render_window', session, nodeId, first, count, dpi),
  renderCompressedWindow: (session, nodeId, dpi, method, first = 0, count = 10) =>
    call('render_compressed_window', session, nodeId, dpi, method, first, count),
  exportPdf: (session, nodeIds = null) => call('export_dialog', session, nodeIds),
  importDialog: (session, parentId = null) => call('import_dialog', session, parentId),
  importBytes: (session, name, data, parentId = null, index = null) => call('import_bytes', session, name, data, parentId, index),
}
