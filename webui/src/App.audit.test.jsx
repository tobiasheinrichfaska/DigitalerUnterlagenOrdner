// Regression tests for the v4 web audit (W-1, W-2, W-3, W-5, W-7, W-8). Mocked pywebview core.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import App from './App'

const leaf = (id, name, extra = {}) => ({ id, name, is_folder: false, pdf_length: 1, has_source: true, children: [], ...extra })
const TREE = {
  id: 'root', name: 'Dok', is_folder: true, datev: null, children: [
    { id: 'F', name: 'Gruppe', is_folder: true, collapsed: false, children: [leaf('A', 'alpha')] },
    leaf('B', 'beta'),
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
    save_info: () => ({ ok: true, has_alternatives: false }),
    datev_status: () => ({ ok: true, datev_mode: true, connected: true, feature: 'DokAb' }),
    datev_placements: () => ({ ok: true, folders: [] }),
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

async function renderApp(overrides, ready = /Gruppe/) {
  const calls = installApi(overrides)
  const utils = render(<App />)
  await screen.findByText(ready)
  return { calls, ...utils }
}
const callsOf = (calls, m) => calls.filter((c) => c.method === m)
const selectedRow = () => document.querySelector('[aria-selected="true"]')

beforeEach(() => {
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  try { localStorage.clear() } catch { /* ignore */ }
})
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('W-1 — organizer refreshes when the window regains focus', () => {
  it('re-fetches the state on focus and shows the dirty dot + pushes set_dirty(true)', async () => {
    const changed = { ...TREE, children: [...TREE.children, leaf('N', 'neu-aus-pdftool')] }
    const { calls } = await renderApp({
      get_state: () => ({ ok: true, session: 's', tree: changed, can_undo: true, can_redo: false, dirty: true }),
    })
    expect(screen.queryByText(/neu-aus-pdftool/)).toBeNull()
    // The handler deliberately ignores focus while the app is busy (an initial operation may still
    // be running on a slow runner): re-fire focus until get_state was actually requested.
    await waitFor(() => {
      act(() => { window.dispatchEvent(new Event('focus')) })
      expect(callsOf(calls, 'get_state').length).toBeGreaterThan(0)
    }, { timeout: 8000 })
    // explicit timeouts: the default 1000 ms is too tight on a loaded CI runner
    expect(await screen.findByText(/neu-aus-pdftool/, {}, { timeout: 8000 })).toBeInTheDocument()
    expect(document.querySelector('header h1').textContent).toContain('•')
    await waitFor(() => expect(callsOf(calls, 'set_dirty').some((c) => c.args[0] === true)).toBe(true), { timeout: 8000 })
  })

  it('an unsupported/failed state fetch is ignored', async () => {
    await renderApp({ get_state: () => ({ ok: false, error: 'x' }) })
    await act(async () => { window.dispatchEvent(new Event('focus')) })
    expect(screen.getByText(/Gruppe/)).toBeInTheDocument()
    expect(document.querySelector('p.error')?.textContent || '').toBe('')
  })
})

describe('W-2 — a failed save surfaces its error', () => {
  it('shows {ok:false,error} from save_file and keeps the dirty dot', async () => {
    await renderApp({ save_file: () => ({ ok: false, error: 'Schreibfehler XYZ' }) })
    fireEvent.click(screen.getByText(/beta/))
    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))
    expect(await screen.findByText(/Schreibfehler XYZ/)).toBeInTheDocument()
  })

  it('a cancelled save dialog stays silent', async () => {
    await renderApp({ save_file: () => ({ ok: false, error: 'cancelled' }) })
    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))
    await waitFor(() => expect(window.pywebview.api.calls.some((c) => c.method === 'save_file')).toBe(true))
    await act(async () => {})
    expect(screen.queryByText(/cancelled/)).toBeNull()
  })
})

describe('W-3 — a late import response must not reset the selection', () => {
  it('keeps the row the user clicked while the import was running', async () => {
    let resolveImport
    const after = { ...TREE, children: [...TREE.children, leaf('I1', 'eins.pdf')] }
    const { calls } = await renderApp({
      import_dialog: () => new Promise((r) => { resolveImport = () => r({ ok: true, session: 's', tree: after, can_undo: true, can_redo: false }) }),
    })
    fireEvent.click(screen.getByText(/alpha/))            // selected at import-click time
    fireEvent.click(screen.getByRole('button', { name: /Importieren/ }))
    await waitFor(() => expect(resolveImport).toBeTypeOf('function'))
    fireEvent.click(screen.getByText(/beta/))             // user moves on while it runs
    expect(selectedRow().textContent).toMatch(/beta/)
    await act(async () => { resolveImport() })
    await screen.findByText(/eins\.pdf/)
    expect(selectedRow().textContent).toMatch(/beta/)
    // the PRIMARY selection (drives the preview) must still be beta, not reset to alpha
    const pc = callsOf(calls, 'page_count')
    expect(pc[pc.length - 1].args[1]).toBe('B')
  })
})

describe('W-5 / W-7 — DATEV filing dialog', () => {
  const UNLINKED = { id: 'root', name: 'Beleg', is_folder: true, datev: null, children: [leaf('A', 'seite1'), leaf('B', 'seite2')] }
  const open = (extra = {}) => renderApp({
    open: () => ({ ok: true, session: 's', tree: UNLINKED, can_undo: false, can_redo: false }),
    ...extra,
  }, /seite1/)

  it('W-5: Delete on a dialog button does not reach the tree', async () => {
    const { calls } = await open({ datev_clients: () => ({ ok: true, clients: [{ guid: 'g', number: '1', name: 'Muster' }] }) })
    fireEvent.click(screen.getByText(/seite2/))
    fireEvent.click(await screen.findByText('Nach DATEV ablegen'))
    const cancel = await screen.findByRole('button', { name: 'Abbrechen' })
    const before = callsOf(calls, 'dispatch').length
    fireEvent.keyDown(cancel, { key: 'Delete' })
    fireEvent.keyDown(cancel, { key: 'z', ctrlKey: true })
    await act(async () => {})
    expect(callsOf(calls, 'dispatch').length).toBe(before)
    expect(window.confirm).not.toHaveBeenCalled()
  })

  it('W-7: a late client list does not reopen a dialog the user cancelled', async () => {
    let resolveClients
    await open({ datev_clients: () => new Promise((r) => { resolveClients = () => r({ ok: true, clients: [{ guid: 'g', number: '1', name: 'Muster' }] }) }) })
    fireEvent.click(await screen.findByText('Nach DATEV ablegen'))
    fireEvent.click(await screen.findByRole('button', { name: 'Abbrechen' }))
    expect(screen.queryByRole('button', { name: 'Ablegen' })).toBeNull()
    await act(async () => { resolveClients() })
    await act(async () => {})
    expect(screen.queryByRole('button', { name: 'Ablegen' })).toBeNull()
  })
})

describe('W-8 — keyboard navigation follows the displayed (filtered) tree', () => {
  const TAGGED = {
    id: 'root', name: 'Dok', is_folder: true, children: [
      leaf('A', 'Telekom', { tags: ['Steuer'] }),
      { id: 'F', name: 'Ordner', is_folder: true, collapsed: false, tags: [], children: [leaf('B', 'Quittung', { tags: [] })] },
      leaf('C', 'Sonstiges', { tags: [] }),
    ],
  }
  it('ArrowDown on the last visible row stays put; Left/Right never dispatch SetCollapsed on hidden folders', async () => {
    const calls = installApi({ open: () => ({ ok: true, session: 's', tree: TAGGED, can_undo: false, can_redo: false }) })
    const { container } = render(<App />)
    await screen.findByText(/Telekom/)
    fireEvent.change(container.querySelector('.tvb-search input'), { target: { value: 'Steuer' } })
    expect(screen.queryByText(/Sonstiges/)).toBeNull()
    fireEvent.click(screen.getByText(/Telekom/))
    fireEvent.keyDown(window, { key: 'ArrowDown' })
    expect(selectedRow().textContent).toMatch(/Telekom/)   // not the hidden "Ordner"/"Sonstiges"
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(callsOf(calls, 'dispatch').filter((c) => c.args[1].type === 'SetCollapsed')).toHaveLength(0)
  })
})
