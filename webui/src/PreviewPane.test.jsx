// Component tests for the presentational right pane: which children show for the
// empty / windowed / legacy-image states, the page-info text, and the zoom bar.
//
// NOTE: no `vi.mock()` here (it does not take effect under this project's `vmThreads`
// Vitest pool — see CLAUDE.md "Two test layers"). Instead we render the REAL children
// against a stubbed `window.pywebview.api` bridge and assert on their root elements
// (.preview-controls / .tag-editor / .win-preview), which is enough to verify
// PreviewPane's own composition logic (which child shows in which state).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { PreviewPane } from './PreviewPane'

// Benign bridge so the real children (PreviewControls / Preview) can mount without
// erroring; page_count > 0 lets the windowed <Preview> render its .win-preview root.
beforeEach(() => {
  const base = {
    page_count: () => ({ ok: true, count: 3 }),
    page_dims: () => ({ ok: true, dims: [] }),
    compress_options: () => ({ ok: true, options: [], original_size: 100 }),
    render_window: () => ({ ok: true, pages: [] }),
    render_compressed_window: () => ({ ok: true, pages: [] }),
  }
  window.pywebview = { api: new Proxy({}, {
    get(_t, prop) {
      if (typeof prop !== 'string' || prop === 'then') return undefined
      return (...args) => (base[prop] || (() => ({ ok: true })))(...args)
    },
  }) }
})
afterEach(() => { cleanup(); delete window.pywebview })

const leaf = { id: 'L', name: 'doc', is_folder: false, pdf_length: 3 }

const renderPane = (props = {}) => {
  const setZoom = vi.fn()
  const utils = render(<PreviewPane
    previewRef={{ current: null }} tagsOn={false} selected={null} docTags={[]}
    dispatch={() => {}} session="s" onPreview={() => {}} defaultDpi={150}
    onCompressionResolved={() => {}} windowed={false} pages={null} pageInfo={null}
    zoom={1} setZoom={setZoom} previewReq={null} onPageInfo={() => {}} busy={0}
    {...props} />)
  return { setZoom, ...utils }
}

describe('PreviewPane — selection states', () => {
  it('prompts to pick a node when nothing is selected', () => {
    const { container } = renderPane({ selected: null })
    expect(screen.getByText('Knoten auswählen für die Vorschau')).toBeInTheDocument()
    expect(container.querySelector('.preview-controls')).toBeNull()
  })

  it('shows the compression controls for a selected node', () => {
    const { container } = renderPane({ selected: leaf })
    expect(container.querySelector('.preview-controls')).toBeInTheDocument()
  })

  it('renders the tag editor only when tagging is on and a node is selected', () => {
    const off = renderPane({ selected: leaf, tagsOn: false })
    expect(off.container.querySelector('.tag-editor')).toBeNull()
    cleanup()
    const on = renderPane({ selected: leaf, tagsOn: true })
    expect(on.container.querySelector('.tag-editor')).toBeInTheDocument()
    expect(on.setZoom).not.toHaveBeenCalled()
  })

  it('mounts the windowed Preview when windowed', async () => {
    const { container } = renderPane({ selected: leaf, windowed: true })
    await waitFor(() => expect(container.querySelector('.win-preview')).toBeInTheDocument())
  })
})

describe('PreviewPane — page info + zoom bar', () => {
  it('shows "Seite n / total" when a page is in view', () => {
    renderPane({ selected: leaf, windowed: true, pageInfo: { page: 2, total: 3 } })
    expect(screen.getByText('Seite 2 / 3')).toBeInTheDocument()
  })

  it('falls back to the total page count when no page is reported', () => {
    renderPane({ selected: leaf, windowed: true, pageInfo: null })
    expect(screen.getByText('3 Seiten')).toBeInTheDocument()
  })

  it('the −/＋/100% buttons drive setZoom', () => {
    const { setZoom } = renderPane({ selected: leaf, windowed: true })
    fireEvent.click(screen.getByTitle('größer'))
    fireEvent.click(screen.getByTitle('kleiner'))
    fireEvent.click(screen.getByTitle('zurücksetzen'))
    expect(setZoom).toHaveBeenCalledTimes(3)
    // the reset button sets an absolute value
    expect(setZoom).toHaveBeenLastCalledWith(1)
  })
})

describe('PreviewPane — legacy image list', () => {
  it('renders one img per page with a zoom-scaled width', () => {
    renderPane({ selected: leaf, windowed: false, pages: ['data:a', 'data:b'], zoom: 1.5 })
    const imgs = screen.getAllByRole('img')
    expect(imgs).toHaveLength(2)
    expect(imgs[0].style.width).toBe('150%')
  })

  it('shows the empty-preview note for a folder / empty node', () => {
    renderPane({ selected: leaf, windowed: false, pages: [], busy: 0 })
    expect(screen.getByText('Keine Vorschau (Ordner oder leer)')).toBeInTheDocument()
  })
})
