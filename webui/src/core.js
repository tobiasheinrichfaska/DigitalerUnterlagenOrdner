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

async function call(method, ...args) {
  const api = await waitForApi()
  return api[method](...args)
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
  testMode: (dpi = 60, maxPages = 3) => call('test_mode', dpi, maxPages),
  pageCount: (session, nodeId) => call('page_count', session, nodeId),
  pageDims: (session, nodeId) => call('page_dims', session, nodeId),
  renderWindow: (session, nodeId, first = 0, count = 10, dpi = 100) =>
    call('render_window', session, nodeId, first, count, dpi),
  exportPdf: (session, nodeIds = null) => call('export_dialog', session, nodeIds),
  importDialog: (session, parentId = null) => call('import_dialog', session, parentId),
  importBytes: (session, name, data, parentId = null, index = null) => call('import_bytes', session, name, data, parentId, index),
}
