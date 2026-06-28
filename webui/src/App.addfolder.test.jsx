// Wiring test for "Neuer Ordner at the selection + naming dialog" (v3.10.0 #8).
// The placement logic is unit-tested in lib/tree.test.js (newFolderTarget); this
// asserts the toolbar button prompts for a name and dispatches AddFolder at the
// right parent/index for the current selection.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const leaf = { id: 'L', name: 'beleg', is_folder: false, pdf_length: 1, has_source: true, children: [] }
const folder = { id: 'F', name: 'Mappe', is_folder: true, children: [] }
const TREE = { id: 'root', name: 'Dok', is_folder: true, children: [leaf, folder] }

function installApi(overrides = {}) {
  const calls = []
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
    set_dirty: () => ({ ok: true }),
    page_count: () => ({ ok: true, count: 1 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    compress_options: () => ({ ok: true, options: [], original_size: 100 }),
    dispatch: () => ({ ok: true, session: 's', tree: TREE, can_undo: true, can_redo: false }),
  }
  const api = new Proxy({ calls }, {
    get(_t, prop) {
      if (prop === 'calls') return calls
      if (typeof prop !== 'string' || prop === 'then') return undefined
      return (...args) => { calls.push({ method: prop, args }); return (overrides[prop] || base[prop] || (() => ({ ok: true })))(...args) }
    },
  })
  window.pywebview = { api }
  return calls
}

const addFolderCmds = (calls) =>
  calls.filter((c) => c.method === 'dispatch').map((c) => c.args[1]).filter((cmd) => cmd.type === 'AddFolder')

const ordnerButton = () => screen.getByRole('button', { name: /Ordner/ })

beforeEach(() => { localStorage.setItem('beleg.lang', 'de') })  // pin German for stable labels
afterEach(() => { delete window.pywebview; vi.restoreAllMocks(); localStorage.clear() })

describe('Neuer Ordner at selection (v3.10.0 #8)', () => {
  it('prompts and adds at the ROOT when nothing is selected', async () => {
    const calls = installApi()
    vi.spyOn(window, 'prompt').mockReturnValue('Steuer 2025')
    render(<App />)
    await screen.findByText(/beleg/)
    fireEvent.click(ordnerButton())
    await waitFor(() => expect(addFolderCmds(calls).length).toBe(1))
    expect(addFolderCmds(calls)[0]).toMatchObject({ parent_id: 'root', index: null, name: 'Steuer 2025' })
  })

  it('adds INSIDE a selected folder', async () => {
    const calls = installApi()
    vi.spyOn(window, 'prompt').mockReturnValue('Unterordner')
    render(<App />)
    fireEvent.click(await screen.findByText(/Mappe/))
    fireEvent.click(ordnerButton())
    await waitFor(() => expect(addFolderCmds(calls).length).toBe(1))
    expect(addFolderCmds(calls)[0]).toMatchObject({ parent_id: 'F', index: null })
  })

  it('adds as a SIBLING after a selected leaf', async () => {
    const calls = installApi()
    vi.spyOn(window, 'prompt').mockReturnValue('Neben')
    render(<App />)
    fireEvent.click(await screen.findByText(/beleg/))
    fireEvent.click(ordnerButton())
    await waitFor(() => expect(addFolderCmds(calls).length).toBe(1))
    expect(addFolderCmds(calls)[0]).toMatchObject({ parent_id: 'root', index: 1 })
  })

  it('does nothing when the naming dialog is cancelled', async () => {
    const calls = installApi()
    vi.spyOn(window, 'prompt').mockReturnValue(null)
    render(<App />)
    await screen.findByText(/beleg/)
    fireEvent.click(ordnerButton())
    await new Promise((r) => setTimeout(r, 30))
    expect(addFolderCmds(calls).length).toBe(0)
  })
})
