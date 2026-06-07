// Component tests for the two interaction paths that pure-logic tests can't cover:
// (1) the proactive no-gain sweep clearing a leaf's front "undecided" dot, and
// (2) the lazy Help modal opening + the 🇩🇪/🇬🇧 flag switching the text.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from './App'

const undecidedLeaf = { id: 'L', name: 'beleg', is_folder: false, pdf_length: 1, has_source: true, compression_undecided: true, children: [] }
const TREE = { id: 'root', name: 'Dok', is_folder: true, children: [undecidedLeaf] }

function installApi(overrides = {}) {
  const calls = []
  const base = {
    config: () => ({ ok: true, dev: false, default_dpi: 150 }),
    open: () => ({ ok: true, session: 's', tree: TREE, can_undo: false, can_redo: false }),
    set_dirty: () => ({ ok: true }),
    page_count: () => ({ ok: true, count: 1 }),
    page_dims: () => ({ ok: true, dims: [] }),
    render_window: () => ({ ok: true, pages: [] }),
    compress_options: () => ({ ok: true, options: [], original_size: 100 }), // no gain by default
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

const callsOf = (calls, m) => calls.filter((c) => c.method === m)

afterEach(() => { delete window.pywebview; vi.restoreAllMocks() })

describe('proactive no-gain sweep', () => {
  it('clears the front undecided dot for a cheap leaf when nothing smaller is found', async () => {
    const calls = installApi() // compress_options → no options (no gain)
    const { container } = render(<App />)
    await screen.findByText(/beleg/)
    // the sweep evaluates the ≤5-page undecided leaf …
    await waitFor(() => expect(callsOf(calls, 'compress_options').length).toBeGreaterThan(0))
    // … and the front "undecided" dot disappears
    await waitFor(() => expect(container.querySelector('.alt-dot')).toBeNull())
  })

  it('keeps the dot when a smaller variant exists', async () => {
    const calls = installApi({ compress_options: () => ({ ok: true, options: [{ method: 'jpg', size: 40 }], original_size: 100 }) })
    const { container } = render(<App />)
    await screen.findByText(/beleg/)
    await waitFor(() => expect(callsOf(calls, 'compress_options').length).toBeGreaterThan(0))
    expect(container.querySelector('.alt-dot')).not.toBeNull() // still undecided → red dot stays
  })
})

describe('Help modal', () => {
  it('opens (lazy) and the flags switch between German and English', async () => {
    installApi()
    render(<App />)
    await screen.findByText(/beleg/)
    fireEvent.click(screen.getByRole('button', { name: /Hilfe|Help/ }))
    // lazy chunk loads, then the German flag shows German content
    fireEvent.click(await screen.findByTitle('Deutsch'))
    expect(await screen.findByText('Überblick')).toBeInTheDocument()
    // English flag → English content
    fireEvent.click(screen.getByTitle('English'))
    expect(await screen.findByText('Overview')).toBeInTheDocument()
  })
})
