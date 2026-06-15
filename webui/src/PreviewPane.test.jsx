// Component tests for the presentational right pane: which children show for the
// empty / windowed / legacy-image states, the page-info text, and the zoom bar.
// The heavy children (PreviewControls, Preview, TagEditor) are stubbed so this
// tests PreviewPane's own composition logic, not their side effects.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'

vi.mock('./PreviewControls', () => ({ PreviewControls: () => <div data-testid="controls" /> }))
vi.mock('./Preview', () => ({ Preview: () => <div data-testid="windowed-preview" /> }))
vi.mock('./TagEditor', () => ({ TagEditor: () => <div data-testid="tag-editor" /> }))

import { PreviewPane } from './PreviewPane'

afterEach(cleanup)

const leaf = { id: 'L', name: 'doc', is_folder: false, pdf_length: 3 }

const renderPane = (props = {}) => {
  const setZoom = vi.fn()
  render(<PreviewPane
    previewRef={{ current: null }} tagsOn={false} selected={null} docTags={[]}
    dispatch={() => {}} session="s" onPreview={() => {}} defaultDpi={150}
    onCompressionResolved={() => {}} windowed={false} pages={null} pageInfo={null}
    zoom={1} setZoom={setZoom} previewReq={null} onPageInfo={() => {}} busy={0}
    {...props} />)
  return { setZoom }
}

describe('PreviewPane — selection states', () => {
  it('prompts to pick a node when nothing is selected', () => {
    renderPane({ selected: null })
    expect(screen.getByText('Knoten auswählen für die Vorschau')).toBeInTheDocument()
    expect(screen.queryByTestId('controls')).toBeNull()
  })

  it('shows the compression controls for a selected node', () => {
    renderPane({ selected: leaf })
    expect(screen.getByTestId('controls')).toBeInTheDocument()
  })

  it('renders the tag editor only when tagging is on and a node is selected', () => {
    const { setZoom } = renderPane({ selected: leaf, tagsOn: true })
    expect(screen.getByTestId('tag-editor')).toBeInTheDocument()
    expect(setZoom).not.toHaveBeenCalled()
  })

  it('mounts the windowed Preview when windowed', () => {
    renderPane({ selected: leaf, windowed: true })
    expect(screen.getByTestId('windowed-preview')).toBeInTheDocument()
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
