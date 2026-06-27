// App-level DATEV-mode integration: the toggle wiring, the connected badge + write-back
// notice, and the key fix from the v3.10.0 audit — a non-ok write-back verdict must OFFER
// the local-save fallback (call save_file), not just show an error. Mocked pywebview core.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const leaf = (id, name) => ({ id, name, is_folder: false, pdf_length: 1, has_source: true, children: [] })
// a DATEV-connected document: the root carries provenance (doc_guid + file_id)
const CONNECTED_TREE = {
  id: 'root', name: 'Rechnung', is_folder: true,
  datev: { doc_guid: 'fa89ad42-8cd4-4828-8234-143161d41985', file_id: 1085411, source_name: 'Rechnung.pdf' },
  children: [leaf('A', 'seite1')],
}
// a NOT-connected document (no provenance on the root) → offers „Nach DATEV ablegen"
const UNLINKED_TREE = { id: 'root', name: 'Beleg', is_folder: true, datev: null, children: [leaf('A', 'seite1')] }

function installApi(overrides = {}) {
  const calls = []
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    datev_status: () => ({ ok: true, datev_mode: true, connected: true, feature: 'DokAb' }),
    open: () => ({ ok: true, session: 's', tree: CONNECTED_TREE, can_undo: false, can_redo: false,
                   datev: { connected: true, source_name: 'Rechnung.pdf', checked_out_at_open: false } }),
    set_dirty: () => ({ ok: true }),
    page_count: () => ({ ok: true, count: 0 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    ...overrides,
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

const renderApp = async (overrides) => {
  const calls = installApi(overrides)
  render(<App />)
  await screen.findByText(/seite1/)
  return calls
}

beforeEach(() => { vi.spyOn(window, 'prompt').mockReturnValue('10001') })
afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

const called = (calls, method) => calls.filter((c) => c.method === method)

describe('App — DATEV mode', () => {
  it('shows the connected badge + write-back action for a DATEV-linked document', async () => {
    await renderApp()
    expect(await screen.findByText(/Mit DATEV verknüpft/)).toBeInTheDocument()
    expect(screen.getByText('Nach DATEV zurückschreiben')).toBeInTheDocument()
  })

  it('the DATEV toggle calls set_datev_mode', async () => {
    const calls = await renderApp()
    fireEvent.click(screen.getByTitle('DATEV-Modus ein-/ausschalten'))
    await waitFor(() => expect(called(calls, 'set_datev_mode').length).toBeGreaterThan(0))
    // toggles to the opposite of the current (on) state
    expect(called(calls, 'set_datev_mode')[0].args[0]).toBe(false)
  })

  it('a successful write-back names the saved file (format explicit) and does NOT Save-As', async () => {
    const calls = await renderApp({
      save_to_datev: () => ({ ok: true, verdict: 'ok', provenance: CONNECTED_TREE.datev,
                              local_saved: 'C:\\Kanzlei\\Rechnung.belegtool', local_kind: 'belegtool' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    // the notice shows the saved file name so the .belegtool/.pdf format is clear
    await screen.findByText(/Nach DATEV zurückgeschrieben · Rechnung\.belegtool/)
    expect(called(calls, 'save_file').length).toBe(0)
  })

  it('a CONFLICT write-back shows the message AND offers the local-save fallback (audit fix)', async () => {
    const calls = await renderApp({
      save_to_datev: () => ({ ok: false, verdict: 'conflict_changed' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    // the fallback save is offered (save_info preflight → save_file), so the edit isn't lost
    await waitFor(() => expect(called(calls, 'save_info').length + called(calls, 'save_file').length)
      .toBeGreaterThan(0))
  })

  it('an ERROR-verdict write-back shows the real cause (not the generic message) and offers local save', async () => {
    // a mid-write network/HTTP failure returns {verdict:"error", error:"…"}; the UI must show
    // the actual cause, not swallow it behind the generic "Write-back failed" key.
    const calls = await renderApp({
      save_to_datev: () => ({ ok: false, verdict: 'error', error: 'Netzwerk nicht erreichbar' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    expect(await screen.findByText(/Netzwerk nicht erreichbar/)).toBeInTheDocument()
    await waitFor(() => expect(called(calls, 'save_info').length + called(calls, 'save_file').length)
      .toBeGreaterThan(0))   // the local-save fallback is still offered
  })

  it('a declined write-back neither errors nor saves locally', async () => {
    const calls = await renderApp({
      save_to_datev: () => ({ ok: false, verdict: 'declined' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    await waitFor(() => expect(called(calls, 'save_to_datev').length).toBe(1))
    expect(called(calls, 'save_info').length + called(calls, 'save_file').length).toBe(0)
  })

  it('write-back OK but local save failed surfaces BOTH facts (DATEV landed + local failed)', async () => {
    // the v3.10.0 parallel-save mode: DATEV landed, but the bound .belegtool couldn't be written.
    // The single visible message must say the write-back succeeded AND that the local save did
    // not — an error alone would read as if the whole write-back failed.
    await renderApp({
      save_to_datev: () => ({ ok: true, verdict: 'ok', provenance: CONNECTED_TREE.datev,
                              local_error: 'Lokales Speichern fehlgeschlagen' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    expect(await screen.findByText(/zurückgeschrieben, aber lokal nicht gespeichert.*Lokales Speichern fehlgeschlagen/))
      .toBeInTheDocument()
  })

  it('a not-connected document files via datev_file with the prompted Mandant', async () => {
    const calls = await renderApp({
      open: () => ({ ok: true, session: 's', tree: UNLINKED_TREE, can_undo: false, can_redo: false }),
      datev_file: () => ({ ok: true, provenance: { doc_guid: 'new-guid', file_id: 1 } }),
    })
    fireEvent.click(screen.getByText('Nach DATEV ablegen'))
    await waitFor(() => expect(called(calls, 'datev_file').length).toBe(1))
    // datev_file(session, clientGuid=null, mandantNumber, …) → the prompted Mandant is arg[2]
    expect(called(calls, 'datev_file')[0].args[2]).toBe('10001')
    await screen.findByText(/In DATEV abgelegt/)
  })

  it('a failed datev_file surfaces the error', async () => {
    await renderApp({
      open: () => ({ ok: true, session: 's', tree: UNLINKED_TREE, can_undo: false, can_redo: false }),
      datev_file: () => ({ ok: false, error: 'Mandant 999 unbekannt' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV ablegen'))
    expect(await screen.findByText(/Mandant 999 unbekannt/)).toBeInTheDocument()
  })

  it('datev_file OK but local save failed surfaces BOTH facts', async () => {
    await renderApp({
      open: () => ({ ok: true, session: 's', tree: UNLINKED_TREE, can_undo: false, can_redo: false }),
      datev_file: () => ({ ok: true, provenance: { doc_guid: 'new-guid', file_id: 1 },
                           local_error: 'Speichern fehlgeschlagen' }),
    })
    fireEvent.click(screen.getByText('Nach DATEV ablegen'))
    expect(await screen.findByText(/abgelegt, aber lokal nicht gespeichert.*Speichern fehlgeschlagen/))
      .toBeInTheDocument()
  })

  it('the checked-out-at-open hint renders from the open response', async () => {
    await renderApp({
      open: () => ({ ok: true, session: 's', tree: CONNECTED_TREE, can_undo: false, can_redo: false,
                     datev: { connected: true, source_name: 'Rechnung.pdf', checked_out_at_open: true } }),
    })
    expect(await screen.findByText(/in DATEV ausgecheckt/)).toBeInTheDocument()
  })

  it('export → DATEV files via datev_export and surfaces a partial-failure message', async () => {
    const calls = await renderApp({
      datev_export: () => ({ ok: false, parts: 2, filed_ok: 1,
                             error: 'Nur 1 von 2 Teil(en) nach DATEV abgelegt' }),
    })
    fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }))            // toolbar export
    // the export-options dialog opens with the DATEV option (connected + mode on)
    fireEvent.click(await screen.findByText(/Nach DATEV ablegen \(gleicher Mandant\)/))
    fireEvent.click(screen.getByRole('button', { name: 'Exportieren' }))           // confirm
    await waitFor(() => expect(called(calls, 'datev_export').length).toBe(1))
    expect(await screen.findByText(/Nur 1 von 2/)).toBeInTheDocument()
  })
})
