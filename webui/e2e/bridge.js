// Injects a stub `window.pywebview.api` before the app loads, so the React SPA runs
// in a plain browser with no Python host. Every call is recorded on `window.__beleg.calls`
// so tests can assert what the UI dispatched. Canned data: a small tree plus a
// multi-page leaf whose pages render as a 1×1 PNG (enough for layout/virtualization).
export async function installBridge(page, { pageCount = 30 } = {}) {
  await page.addInitScript((pageCount) => {
    const leaf = (id, name) => ({ id, name, is_folder: false, pdf_length: pageCount, has_source: true, children: [] })
    const TREE = {
      id: 'root', name: 'Dok', is_folder: true,
      children: [leaf('A', 'alpha'), leaf('B', 'beta'), leaf('C', 'gamma')],
    }
    const calls = []
    window.__beleg = { calls }
    const PX = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    const base = {
      config: () => ({ ok: true, dev: false, default_dpi: 150 }),
      open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
      dispatch: () => ({ ok: true, session: 's', tree: TREE, can_undo: true, can_redo: false }),
      set_dirty: () => ({ ok: true }),
      page_count: () => ({ ok: true, count: pageCount }),
      page_dims: () => ({ ok: true, dims: Array.from({ length: pageCount }, () => [595, 842]) }),
      render_window: (s, id, first, count) => ({ ok: true, pages: Array.from({ length: count }, () => PX) }),
      render_stats: () => ({ ok: true, cache_used: 0, cache_budget: 200 * 1024 * 1024, cache_free: 200 * 1024 * 1024, cache_pages: 0, prefetch_active: false }),
    }
    const api = new Proxy({}, {
      get(_t, prop) {
        if (typeof prop !== 'string' || prop === 'then') return undefined
        return (...args) => { calls.push({ method: prop, args }); return (base[prop] || (() => ({ ok: true })))(...args) }
      },
    })
    window.pywebview = { api }
  }, pageCount)
}
