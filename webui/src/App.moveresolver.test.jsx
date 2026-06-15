// The keyboard Insert multi-move and drag-and-drop share ONE path: App.onMoveMany
// → resolveSel → the same window.confirm prompts. These tests prove the keyboard
// carry triggers the partial-folder warning (a folder is in the selection but only
// SOME of its children are) and honours each choice — exactly like a drag drop.
//
// Tree:  root → [ Z(leaf), F(folder) → [C1, C2], W(leaf) ]
// Select C1 + F + Z (so F is "partial": C1 selected, C2 not), primary = Z.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const leaf = (id, name) => ({ id, name, is_folder: false, pdf_length: 1, has_source: true, children: [] })
const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    leaf('Z', 'zeta'),
    { id: 'F', name: 'Mappe', is_folder: true, collapsed: false, children: [leaf('C1', 'kind1'), leaf('C2', 'kind2')] },
    leaf('W', 'wonne'),
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

const lastMoveMany = () =>
  [...window.pywebview.api.calls].reverse().find((c) => c.args?.[1]?.type === 'MoveMany')?.args?.[1]
const moveManyCount = () => window.pywebview.api.calls.filter((c) => c.args?.[1]?.type === 'MoveMany').length

// select C1 + F + Z (primary = Z, idx 0), then carry it down one and drop
async function carryPartialSelection() {
  installApi()
  render(<App />)
  await screen.findByText(/zeta/)
  fireEvent.click(screen.getByText(/kind1/))                 // C1 (inside F)
  fireEvent.click(screen.getByText(/Mappe/), { ctrlKey: true }) // F (folder)
  fireEvent.click(screen.getByText(/zeta/), { ctrlKey: true })   // Z (primary)
  fireEvent.keyDown(window, { key: 'Insert' })
  fireEvent.keyDown(window, { key: 'ArrowDown' })            // primary Z moves down
  fireEvent.keyDown(window, { key: 'Insert' })               // drop → onMoveMany → resolveSel
}

afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('keyboard multi-move — partial-folder resolver (parity with drag)', () => {
  it('warns when a selected folder has only SOME children selected', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    await carryPartialSelection()
    await waitFor(() => expect(moveManyCount()).toBeGreaterThan(0))
    // the very first prompt is the "include whole folder?" partial warning, named with the folder
    expect(confirm.mock.calls[0][0]).toMatch(/Mappe/)
    expect(confirm.mock.calls[0][0]).toMatch(/den ganzen Ordner einbeziehen/)
  })

  it('choosing "include whole folder" keeps F, drops the redundant child C1', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true) // first prompt → "all"
    await carryPartialSelection()
    await waitFor(() => expect(lastMoveMany()).toBeTruthy())
    expect(lastMoveMany()).toMatchObject({ type: 'MoveMany', node_ids: ['F', 'Z'], new_parent_id: 'root', index: 2 })
  })

  it('choosing "only the selected items" excludes the folder, keeps C1', async () => {
    // partial ask: confirm("all?")→false, then confirm("exclude?")→true
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true)
    await carryPartialSelection()
    await waitFor(() => expect(lastMoveMany()).toBeTruthy())
    expect(lastMoveMany().node_ids.sort()).toEqual(['C1', 'Z'])
  })

  it('aborting the resolver dispatches nothing', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false) // all?→no, exclude?→no ⇒ abort
    await carryPartialSelection()
    // give the async drop a tick; nothing should be dispatched
    await new Promise((r) => setTimeout(r, 60))
    expect(moveManyCount()).toBe(0)
  })
})
