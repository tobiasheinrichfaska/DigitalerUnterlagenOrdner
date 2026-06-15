// Component tests for the tag-view control bar: search box + clear button, the
// group-by-tag toggle, and the active-view hint (different text for filter vs
// group) with its "open in new window" / "reset view" actions. Pure props,
// German source strings (no provider).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { TagViewBar } from './TagViewBar'

afterEach(cleanup)

const renderBar = (props = {}) => {
  const handlers = {
    setSearch: vi.fn(), setGrouped: vi.fn(), onReset: vi.fn(), onOpenInNewWindow: vi.fn(),
  }
  render(<TagViewBar search="" grouped={false} active={false} {...handlers} {...props} />)
  return handlers
}

describe('TagViewBar — search', () => {
  it('typing reports the new search text', () => {
    const { setSearch } = renderBar()
    fireEvent.change(screen.getByLabelText('Tags suchen…'), { target: { value: 'rechnung' } })
    expect(setSearch).toHaveBeenCalledWith('rechnung')
  })

  it('the clear button shows only when there is a query and clears it', () => {
    const { setSearch } = renderBar({ search: 'x' })
    fireEvent.click(screen.getByTitle('Suche löschen'))
    expect(setSearch).toHaveBeenCalledWith('')
  })

  it('no clear button when the query is empty', () => {
    renderBar({ search: '' })
    expect(screen.queryByTitle('Suche löschen')).toBeNull()
  })
})

describe('TagViewBar — group toggle', () => {
  it('toggling group-by-tag reports the new boolean', () => {
    const { setGrouped } = renderBar({ grouped: false })
    fireEvent.click(screen.getByRole('checkbox'))
    expect(setGrouped).toHaveBeenCalledWith(true)
  })
})

describe('TagViewBar — active-view hint', () => {
  it('hidden when no view is active', () => {
    renderBar({ active: false })
    expect(screen.queryByText('Ansicht zurücksetzen')).toBeNull()
  })

  it('shows the filter hint and reset/open actions when active (not grouped)', () => {
    const { onReset, onOpenInNewWindow } = renderBar({ active: true, grouped: false })
    expect(screen.getByText(/Ansicht gefiltert/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('In neuem Fenster öffnen'))
    expect(onOpenInNewWindow).toHaveBeenCalled()
    fireEvent.click(screen.getByText('Ansicht zurücksetzen'))
    expect(onReset).toHaveBeenCalled()
  })

  it('shows the group-specific hint text when grouped', () => {
    renderBar({ active: true, grouped: true })
    expect(screen.getByText(/Nach Tag gruppiert/)).toBeInTheDocument()
  })

  it('omits the "open in new window" action when no handler is given', () => {
    renderBar({ active: true, onOpenInNewWindow: undefined })
    expect(screen.queryByText('In neuem Fenster öffnen')).toBeNull()
    expect(screen.getByText('Ansicht zurücksetzen')).toBeInTheDocument()
  })
})
