// App-level integration tests for tree selection: plain click (single),
// Ctrl/Cmd-click (toggle add/remove), and Shift-click (range over the VISIBLE
// pre-order). Selection is asserted through `aria-selected` on each treeitem —
// the source of truth the UI and screen readers both read — and the preview
// "primary" node through the `.row.primary` class. Mocked pywebview core.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

// root
//  ├ alpha   (leaf)
//  ├ beta    (leaf)
//  ├ gamma   (leaf)
//  └ Gruppe  (folder, expanded)
//      └ delta (leaf)
// visible pre-order: alpha, beta, gamma, Gruppe, delta
const leaf = (id, name) => ({ id, name, is_folder: false, pdf_length: 1, has_source: true, children: [] })
const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    leaf('A', 'alpha'), leaf('B', 'beta'), leaf('C', 'gamma'),
    { id: 'G', name: 'Gruppe', is_folder: true, collapsed: false, children: [leaf('D', 'delta')] },
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

async function renderApp() {
  installApi()
  render(<App />)
  await screen.findByText(/alpha/)
}

const rowOf = (name) => screen.getByText(new RegExp(name)).closest('[role="treeitem"]')
const isSel = (name) => rowOf(name).getAttribute('aria-selected') === 'true'
const selCount = () => document.querySelectorAll('[role="treeitem"][aria-selected="true"]').length
const primaryText = () => document.querySelector('.row.primary')?.textContent

beforeEach(() => { vi.spyOn(window, 'confirm').mockReturnValue(true) })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('selection — plain click', () => {
  it('selects exactly the clicked node and makes it primary', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/beta/))
    expect(isSel('beta')).toBe(true)
    expect(selCount()).toBe(1)
    expect(primaryText()).toMatch(/beta/)
  })
})

describe('selection — Ctrl/Cmd-click (toggle)', () => {
  it('adds further nodes to the selection', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))
    fireEvent.click(screen.getByText(/gamma/), { ctrlKey: true })
    expect(isSel('alpha')).toBe(true)
    expect(isSel('gamma')).toBe(true)
    expect(selCount()).toBe(2)
  })

  it('Cmd (metaKey) behaves like Ctrl on mac', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))
    fireEvent.click(screen.getByText(/beta/), { metaKey: true })
    expect(selCount()).toBe(2)
  })

  it('Ctrl-clicking an already-selected node removes it; primary falls back to the last remaining', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))
    fireEvent.click(screen.getByText(/beta/), { ctrlKey: true })   // [alpha, beta]
    fireEvent.click(screen.getByText(/alpha/), { ctrlKey: true })  // remove alpha → [beta]
    expect(isSel('alpha')).toBe(false)
    expect(isSel('beta')).toBe(true)
    expect(selCount()).toBe(1)
    expect(primaryText()).toMatch(/beta/)
  })
})

describe('selection — Shift-click (range)', () => {
  it('selects the contiguous range over the visible pre-order from the anchor', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))                      // anchor = alpha
    fireEvent.click(screen.getByText(/gamma/), { shiftKey: true })  // alpha..gamma
    expect(isSel('alpha')).toBe(true)
    expect(isSel('beta')).toBe(true)
    expect(isSel('gamma')).toBe(true)
    expect(isSel('Gruppe')).toBe(false)
    expect(isSel('delta')).toBe(false)
    expect(selCount()).toBe(3)
  })
})

describe('selection + Insert carry-move (multi-node)', () => {
  const lastDispatch = () => {
    const calls = window.pywebview.api.calls
    return [...calls].reverse().find((c) => c.method === 'dispatch')?.args?.[1]
  }
  const singleMoveCount = () => window.pywebview.api.calls.filter((c) => c.args?.[1]?.type === 'Move').length

  // A multi-selection is "locked in" by Insert: the primary moves optically while the
  // rest stay visibly selected, and the whole block follows on drop as ONE undoable
  // MoveMany. node_ids land contiguously at the primary's drop slot (the core discounts
  // the moved-out siblings before it), so [alpha, gamma] reorder to sit before beta.
  it('Insert→Arrow→Insert moves the WHOLE selection as one MoveMany', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))                    // [alpha] (A, idx 0)
    fireEvent.click(screen.getByText(/gamma/), { ctrlKey: true }) // [alpha, gamma], primary = gamma (C, idx 2)
    expect(selCount()).toBe(2)

    fireEvent.keyDown(window, { key: 'Insert' })   // grab the block (primary = gamma)
    fireEvent.keyDown(window, { key: 'ArrowUp' })  // primary moves optically (idx 2 → before beta)
    fireEvent.keyDown(window, { key: 'Insert' })   // drop → one MoveMany

    await waitFor(() =>
      expect(lastDispatch()).toMatchObject({ type: 'MoveMany', node_ids: ['A', 'C'], new_parent_id: 'root', index: 1 }))
    expect(singleMoveCount()).toBe(0)              // not a single-node Move
  })

  it('a single-node Insert carry still dispatches a plain Move (no MoveMany)', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/gamma/))     // single selection (C, idx 2)
    fireEvent.keyDown(window, { key: 'Insert' })
    fireEvent.keyDown(window, { key: 'ArrowUp' })
    fireEvent.keyDown(window, { key: 'Insert' })
    await waitFor(() => expect(lastDispatch()).toMatchObject({ type: 'Move', node_id: 'C' }))
    expect(window.pywebview.api.calls.filter((c) => c.args?.[1]?.type === 'MoveMany').length).toBe(0)
  })
})

describe('selection — collapse back to single', () => {
  it('a plain click after a multi-selection selects only the clicked node', async () => {
    await renderApp()
    fireEvent.click(screen.getByText(/alpha/))
    fireEvent.click(screen.getByText(/gamma/), { shiftKey: true })  // [alpha, beta, gamma]
    expect(selCount()).toBe(3)
    fireEvent.click(screen.getByText(/delta/))                      // plain click on a non-primary node
    expect(selCount()).toBe(1)
    expect(isSel('delta')).toBe(true)
  })
})
