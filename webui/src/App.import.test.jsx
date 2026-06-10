// App-level UI tests for the IMPORT flow with fake (mocked) imports — the import
// button and OS file drag-drop — without a real backend / data model.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const TREE = {
  id: 'root', name: 'Dok', is_folder: true, children: [
    { id: 'F', name: 'Gruppe', is_folder: true, collapsed: false, children: [] },
    { id: 'B', name: 'beta', is_folder: false, pdf_length: 1, has_source: true, children: [] },
  ],
}
// tree the import endpoints "return" — two imported siblings at the same level
const TREE_AFTER = {
  ...TREE,
  children: [
    ...TREE.children,
    { id: 'I1', name: 'eins.pdf', is_folder: false, pdf_length: 1, has_source: true, children: [] },
    { id: 'I2', name: 'zwei.pdf', is_folder: false, pdf_length: 1, has_source: true, children: [] },
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
    import_dialog: () => ({ ok: true, session: 's', tree: TREE_AFTER, can_undo: true, can_redo: false }),
    import_bytes: () => ({ ok: true, session: 's', tree: TREE_AFTER, can_undo: true, can_redo: false }),
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

async function renderApp(overrides) {
  const calls = installApi(overrides)
  render(<App />)
  await screen.findByText(/Gruppe/)
  return calls
}

const callsOf = (calls, m) => calls.filter((c) => c.method === m)

beforeEach(() => { vi.spyOn(window, 'confirm').mockReturnValue(true) })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('App import — toolbar button', () => {
  it('imports into the root when nothing/leaf is selected, and shows the new nodes', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByText(/Importieren/))
    await waitFor(() => expect(callsOf(calls, 'import_dialog').length).toBe(1))
    expect(callsOf(calls, 'import_dialog')[0].args[1]).toBeNull()  // target = null (root)
    expect(await screen.findByText(/eins\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/zwei\.pdf/)).toBeInTheDocument()
  })

  it('imports into the selected folder', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByText(/Gruppe/))   // select the folder
    fireEvent.click(screen.getByText(/Importieren/))
    await waitFor(() => expect(callsOf(calls, 'import_dialog').length).toBe(1))
    expect(callsOf(calls, 'import_dialog')[0].args[1]).toBe('F')
  })
})

describe('App import — partial import warning', () => {
  it('shows the composed warning in an aria-live error paragraph (localized at render)', async () => {
    const calls = await renderApp({
      import_dialog: () => ({ ok: true, session: 's', tree: TREE_AFTER, can_undo: true, can_redo: false,
        warning: 'geheim.pdf: Datei ist passwortgeschützt' }),
    })
    fireEvent.click(screen.getByText(/Importieren/))
    await waitFor(() => expect(callsOf(calls, 'import_dialog').length).toBe(1))
    // default language is German (the source), so the composite renders as-is;
    // the English mapping of these templates is locked in lib/messages.test.js
    const err = await screen.findByText(/Teilweise importiert — geheim\.pdf: Datei ist passwortgeschützt/)
    expect(err.closest('p.error')).toHaveAttribute('aria-live', 'polite')
  })
})

describe('App import — OS file drag-drop (fake files)', () => {
  it('drops two fake files: placeholders appear, each is imported, then they land as siblings', async () => {
    const calls = await renderApp()
    const files = [new File(['a'], 'eins.pdf'), new File(['b'], 'zwei.pdf')]
    fireEvent.drop(window, { dataTransfer: { files, types: ['Files'] } })

    // both dropped files show as progress placeholders immediately (same level)
    expect(await screen.findByText(/eins\.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/zwei\.pdf/)).toBeInTheDocument()

    // each file is imported via import_bytes (sequentially, order preserved)
    await waitFor(() => expect(callsOf(calls, 'import_bytes').length).toBe(2))
    expect(callsOf(calls, 'import_bytes').map((c) => c.args[1])).toEqual(['eins.pdf', 'zwei.pdf'])
    // multiple files append (index null) so they don't collide / stagger
    for (const c of callsOf(calls, 'import_bytes')) expect(c.args[4]).toBeNull()
  })
})
