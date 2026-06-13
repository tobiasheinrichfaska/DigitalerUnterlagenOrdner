// Regression test for the Ctrl+wheel preview-zoom gesture.
//
// A prior refactor changed the wheel listener's useEffect deps to [], so it ran exactly
// once — during the "Verbinde mit Core…" loading screen, before the preview element
// existed. It bailed on the null ref and never re-bound, silently killing Ctrl+wheel zoom
// for the whole session. The fix binds via a callback ref (attaches when the element
// mounts). This test locks the behaviour: Ctrl+wheel changes the zoom %, a plain wheel
// (no Ctrl) does not.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import App from './App'

const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    { id: 'B', name: 'beta', is_folder: false, pdf_length: 1, has_source: true, children: [] },
  ],
}

function installApi() {
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
    page_count: () => ({ ok: true, count: 1 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    render: () => ({ ok: true, pages: [] }),
    compress_options: () => ({ ok: true, options: [], original_size: 0 }),
  }
  window.pywebview = {
    api: new Proxy({}, {
      get(_t, prop) {
        if (typeof prop !== 'string' || prop === 'then') return undefined
        return (...args) => (base[prop] || (() => ({ ok: true })))(...args)
      },
    }),
  }
}

afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('App — Ctrl+wheel preview zoom (regression)', () => {
  it('Ctrl+wheel up zooms in; a plain wheel does not', async () => {
    installApi()
    render(<App />)
    await screen.findByText(/beta/) // config+open resolved
    fireEvent.click(screen.getByText(/beta/)) // select the leaf → preview pane + zoom bar

    const pane = document.querySelector('.preview-pane')
    expect(pane).toBeTruthy()
    // "100%" appears twice at rest (the zoom readout span + the reset button label), so we
    // assert on the unique post-zoom readout instead. It must be absent before the gesture.
    expect(screen.queryByText('115%')).toBeNull()

    // Ctrl+wheel up (deltaY < 0) → +0.15 → 115%. If the listener were not bound (the
    // regression), this would do nothing and "115%" would never appear.
    fireEvent.wheel(pane, { deltaY: -100, ctrlKey: true })
    expect(await screen.findByText('115%')).toBeInTheDocument()

    // A wheel WITHOUT Ctrl must not change the zoom (handler returns early).
    fireEvent.wheel(pane, { deltaY: -100 })
    expect(screen.getByText('115%')).toBeInTheDocument()
  })
})
