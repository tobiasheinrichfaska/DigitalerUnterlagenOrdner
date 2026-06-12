// App-level UI tests for keyboard navigation, optical carry-move, and folder
// collapse — with a mocked pywebview core (no real backend / data model).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

// root
//  ├ Gruppe (folder, expanded)
//  │   └ alpha
//  └ beta
const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    { id: 'F', name: 'Gruppe', is_folder: true, collapsed: false, children: [
      { id: 'A', name: 'alpha', is_folder: false, pdf_length: 1, has_source: true, children: [] },
    ] },
    { id: 'B', name: 'beta', is_folder: false, pdf_length: 1, has_source: true, children: [] },
  ],
}

function installApi() {
  const calls = []
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
    dispatch: () => ({ ok: true, session: 's', tree: TREE, can_undo: true, can_redo: false }),
    set_dirty: () => ({ ok: true }),
    page_count: () => ({ ok: true, count: 0 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    render: () => ({ ok: true, pages: [] }),
  }
  const api = new Proxy({ calls }, {
    get(t, prop) {
      if (prop === 'calls') return calls
      if (typeof prop !== 'string' || prop === 'then') return undefined
      return (...args) => { calls.push({ method: prop, args }); return (base[prop] || (() => ({ ok: true })))(...args) }
    },
  })
  window.pywebview = { api }
  return calls
}

const lastDispatch = (calls) => [...calls].reverse().find((c) => c.method === 'dispatch')?.args?.[1]

async function renderApp() {
  const calls = installApi()
  render(<App />)
  await screen.findByText(/Gruppe/) // wait for config+open to resolve and the tree to render
  return calls
}

beforeEach(() => { vi.spyOn(window, 'confirm').mockReturnValue(true) })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('App keyboard — modal gating', () => {
  it('Delete / Ctrl+S / ArrowDown do nothing while the export dialog is open', async () => {
    const calls = await renderApp()
    // Select beta so Delete would normally dispatch
    fireEvent.click(screen.getByText(/beta/))
    // Click the Export PDF toolbar button — this synchronously opens the ExportDialog
    // (exportPdf() just calls setExportAsk({ids}) — no async, no bridge call)
    fireEvent.click(screen.getByText(/Export PDF/))
    // Dialog is now open — the export dialog h2 should be visible
    expect(screen.getByText('PDF exportieren')).toBeInTheDocument()
    // Snapshot dispatch count before firing keyboard events
    const countBefore = calls.filter((c) => c.method === 'dispatch').length
    // All of these must be swallowed by the modal gate in useKeyboard
    fireEvent.keyDown(window, { key: 'Delete' })
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    fireEvent.keyDown(window, { key: 's', ctrlKey: true })
    const countAfter = calls.filter((c) => c.method === 'dispatch').length
    expect(countAfter).toBe(countBefore) // no new dispatches while dialog is open
  })
})

describe('App keyboard — navigation', () => {
  it('ArrowDown moves the selection to the next visible node', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/Gruppe/))         // select folder F
    fireEvent.keyDown(window, { key: 'ArrowDown' })      // → a (F is expanded)
    await waitFor(() =>
      expect(document.querySelector('.row.primary')?.textContent).toMatch(/alpha/))
  })
})

describe('App keyboard — folder collapse via ←', () => {
  it('ArrowLeft on an expanded folder dispatches SetCollapsed', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByText(/Gruppe/))
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    await waitFor(() =>
      expect(lastDispatch(calls)).toEqual({ type: 'SetCollapsed', node_id: 'F', collapsed: true }))
  })
})

describe('App keyboard — optical carry-move', () => {
  it('Insert → ArrowUp → Insert commits a single Move; nothing before the drop', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByText(/beta/))          // select leaf b (index 1 under root)
    fireEvent.keyDown(window, { key: 'Insert' })           // grab
    fireEvent.keyDown(window, { key: 'ArrowUp' })          // move OPTICALLY (no dispatch yet)
    expect(lastDispatch(calls)).toBeUndefined()
    fireEvent.keyDown(window, { key: 'Insert' })           // drop → one Move
    await waitFor(() =>
      expect(lastDispatch(calls)).toEqual({ type: 'Move', node_id: 'B', new_parent_id: 'root', index: 0 }))
  })

  it('Escape cancels the carry without dispatching', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByText(/beta/))
    fireEvent.keyDown(window, { key: 'Insert' })
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    fireEvent.keyDown(window, { key: 'Escape' })
    fireEvent.keyDown(window, { key: 'Insert' }) // would re-grab, but no drop happened
    expect(lastDispatch(calls)).toBeUndefined()
  })
})
