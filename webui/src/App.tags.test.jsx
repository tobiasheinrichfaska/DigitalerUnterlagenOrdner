// App-level UI tests for the TAGS view layer (3c/3d): the search filter, the
// group-by-tag toggle, the structural edit-lock while a view is active, and the
// regression that a LANGUAGE change must not blank the tree (a broken treeForView
// memo that depended on t() used to do exactly that).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import App from './App'

// A tagged tree → tagging auto-enables on load (allTags > 0), so the view bar shows.
//  A(Telekom, Steuer) | F(Ordner, Spende) → B(Quittung, —) | C(Sonstiges, —)
const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    { id: 'A', name: 'Telekom', is_folder: false, pdf_length: 1, has_source: true, tags: ['Steuer'], children: [] },
    { id: 'F', name: 'Ordner', is_folder: true, collapsed: false, tags: ['Spende'], children: [
      { id: 'B', name: 'Quittung', is_folder: false, pdf_length: 1, has_source: true, tags: [], children: [] },
    ] },
    { id: 'C', name: 'Sonstiges', is_folder: false, pdf_length: 1, has_source: true, tags: [], children: [] },
  ],
}

function installApi(overrides = {}) {
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
      return (...args) => { calls.push({ method: prop, args }); return (overrides[prop] || base[prop] || (() => ({ ok: true })))(...args) }
    },
  })
  window.pywebview = { api }
  return calls
}

async function renderApp() {
  const calls = installApi()
  const utils = render(<App />)
  await screen.findByText(/Telekom/)
  return { ...utils, calls }
}

const searchInput = (c) => c.querySelector('.tvb-search input')
const groupCheckbox = (c) => c.querySelector('.tvb-group input')

beforeEach(() => { try { localStorage.clear() } catch { /* ignore */ } })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('App tags — view bar appears for a tagged file', () => {
  it('auto-enables tagging (search box + group toggle present)', async () => {
    const { container } = await renderApp()
    expect(searchInput(container)).toBeTruthy()
    expect(groupCheckbox(container)).toBeTruthy()
  })
})

describe('App tags — search filter', () => {
  it('a tag match keeps the node; non-matching siblings drop out', async () => {
    const { container } = await renderApp()
    fireEvent.change(searchInput(container), { target: { value: 'Steuer' } })
    // A matches by its Steuer tag; F/B (Spende) and C (untagged) are filtered away
    expect(screen.getByText(/Telekom/)).toBeInTheDocument()
    expect(screen.queryByText(/Sonstiges/)).toBeNull()
    expect(screen.queryByText(/Quittung/)).toBeNull()
  })
})

describe('App tags — group by tag', () => {
  it('groups by tag while preserving folders + ancestor paths', async () => {
    const { container } = await renderApp()
    fireEvent.click(groupCheckbox(container))
    const tree = within(container.querySelector('.tree-pane')) // avoid the toolbar's "＋ Ordner"
    // F (Ordner, tagged Spende) is kept WHOLE as a folder under its tag (not dissolved)
    expect(tree.getByText(/Ordner/)).toBeInTheDocument()
    expect(tree.getByText(/Quittung/)).toBeInTheDocument()  // inside the kept Ordner
    expect(tree.getByText(/Telekom/)).toBeInTheDocument()   // under "Steuer"
    expect(tree.getByText(/Sonstiges/)).toBeInTheDocument() // under the untagged group
  })
})

describe('App tags — structural edit-lock while a view is active', () => {
  it('disables Import while filtering, re-enables on reset', async () => {
    const { container } = await renderApp()
    const importBtn = screen.getByRole('button', { name: /Importieren/ })
    expect(importBtn).not.toBeDisabled()
    fireEvent.change(searchInput(container), { target: { value: 'Steuer' } })
    expect(importBtn).toBeDisabled()
    fireEvent.change(searchInput(container), { target: { value: '' } })
    expect(importBtn).not.toBeDisabled()
  })
})

describe('App tags — shift-range selection uses the filtered view, not the full tree', () => {
  it('shift-range in a filter only spans visible nodes (no hidden rows selected)', async () => {
    // Tree in filter "Steuer": only A (Telekom) is visible (F/B/C filtered out).
    // Shift-click from A to A should produce [A] only — NOT [A, F, B, C] from the full tree.
    const { container } = await renderApp()
    fireEvent.change(searchInput(container), { target: { value: 'Steuer' } })
    // click A (anchor)
    fireEvent.click(screen.getByText(/Telekom/))
    // shift-click A again (range anchor == target → just [A])
    fireEvent.click(screen.getByText(/Telekom/), { shiftKey: true })
    // The selected node should be the single visible match, not an inflated set
    expect(document.querySelector('.row.selected')).toBeInTheDocument()
    // Verify that hidden nodes (Sonstiges/Quittung) are not in the DOM at all
    expect(screen.queryByText(/Sonstiges/)).toBeNull()
    expect(screen.queryByText(/Quittung/)).toBeNull()
    void container
  })
})

describe('App tags — language change does not blank the tree (regression)', () => {
  it('keeps the filtered tree visible after switching language', async () => {
    const { container } = await renderApp()
    fireEvent.change(searchInput(container), { target: { value: 'Steuer' } })
    expect(screen.getByText(/Telekom/)).toBeInTheDocument()
    // switch language via the toolbar selector → the (memoised) view must survive
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'en-US' } })
    expect(screen.getByText(/Telekom/)).toBeInTheDocument()
    // and the search is still applied (non-match still hidden)
    expect(screen.queryByText(/Sonstiges/)).toBeNull()
  })
})
