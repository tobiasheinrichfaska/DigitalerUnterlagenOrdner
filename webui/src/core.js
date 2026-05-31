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
  open: (session = null, path = null) => call('open', session, path),
  dispatch: (session, command) => call('dispatch', session, command),
  undo: (session) => call('undo', session),
  redo: (session) => call('redo', session),
}
