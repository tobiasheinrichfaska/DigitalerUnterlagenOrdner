// Audit aa4: Ctrl+S key-repeat / double click must not queue a flood of saves (HA-1c),
// and a failed new_window must be shown (HA-5). Mocked pywebview core, no vi.mock.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const TREE = { id: 'root', name: 'Dok', is_folder: true, children: [
  { id: 'B', name: 'beta', is_folder: false, pdf_length: 1, has_source: true, children: [] }] }

function installApi(overrides = {}) {
  const calls = []
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
    set_dirty: () => ({ ok: true }),
    page_count: () => ({ ok: true, count: 0 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    save_info: () => ({ ok: true, has_alternatives: false }),
    ...overrides,
  }
  window.pywebview = { api: new Proxy({ calls }, {
    get(_t, prop) {
      if (prop === 'calls') return calls
      if (typeof prop !== 'string' || prop === 'then') return undefined
      return (...args) => { calls.push({ method: prop, args }); return (base[prop] || (() => ({ ok: true })))(...args) }
    },
  }) }
  return calls
}
const n = (calls, m) => calls.filter((c) => c.method === m).length

beforeEach(() => { localStorage.setItem('beleg.lang', 'de') })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks(); localStorage.clear() })

describe('save in-flight guard (aa4 HA-1c)', () => {
  it('ignores auto-repeated Ctrl+S key events', async () => {
    const calls = installApi()
    render(<App />)
    await screen.findByText(/beta/)
    fireEvent.keyDown(window, { key: 's', ctrlKey: true, repeat: true })
    fireEvent.keyDown(window, { key: 's', ctrlKey: true, repeat: true })
    await new Promise((r) => setTimeout(r, 30))
    expect(n(calls, 'save_file')).toBe(0)
  })

  it('a second Ctrl+S while the first save is still running does not start another', async () => {
    let release
    const calls = installApi({ save_file: () => new Promise((res) => { release = () => res({ ok: true }) }) })
    render(<App />)
    await screen.findByText(/beta/)
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })
    await waitFor(() => expect(n(calls, 'save_file')).toBe(1))
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })
    await new Promise((r) => setTimeout(r, 30))
    expect(n(calls, 'save_file')).toBe(1)
    release()
    await new Promise((r) => setTimeout(r, 30))
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })  // free again after completion
    await waitFor(() => expect(n(calls, 'save_file')).toBe(2))
  })
})

describe('new window failure (aa4 HA-5)', () => {
  it('shows the error when new_window returns ok:false', async () => {
    installApi({ new_window: () => ({ ok: false, error: 'Fenster-Fehler XYZ' }) })
    render(<App />)
    await screen.findByText(/beta/)
    fireEvent.keyDown(window, { key: 'n', ctrlKey: true })
    expect(await screen.findByText(/Fenster-Fehler XYZ/)).toBeInTheDocument()
  })
})
