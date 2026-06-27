// DatevBar component tests (rendered without a LanguageProvider → German source
// strings). Covers the toggle, the connected badge + write-back action, and the
// not-connected file action.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { DatevBar } from './DatevBar'

afterEach(cleanup)

const render_ = (props = {}) => {
  const handlers = { onToggleMode: vi.fn(), onSaveBack: vi.fn(), onFile: vi.fn() }
  render(<DatevBar datevMode={false} connected={false} busy={false} {...handlers} {...props} />)
  return handlers
}

describe('DatevBar', () => {
  it('always shows the DATEV-mode toggle and fires onToggleMode', () => {
    const h = render_({ datevMode: false })
    const toggle = screen.getByTitle('DATEV-Modus ein-/ausschalten')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(toggle)
    expect(h.onToggleMode).toHaveBeenCalled()
  })

  it('marks the toggle pressed when mode is on', () => {
    render_({ datevMode: true })
    expect(screen.getByTitle('DATEV-Modus ein-/ausschalten'))
      .toHaveAttribute('aria-pressed', 'true')
  })

  it('off: shows neither the write-back nor the file action', () => {
    render_({ datevMode: false, connected: true })
    expect(screen.queryByText('Nach DATEV zurückschreiben')).toBeNull()
    expect(screen.queryByText('Nach DATEV ablegen')).toBeNull()
  })

  it('on + connected: shows the linked badge + write-back, fires onSaveBack', () => {
    const h = render_({ datevMode: true, connected: true, sourceName: 'Rechnung.pdf' })
    expect(screen.getByText(/Mit DATEV verknüpft/)).toBeInTheDocument()
    expect(screen.getByText(/Rechnung\.pdf/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('Nach DATEV zurückschreiben'))
    expect(h.onSaveBack).toHaveBeenCalled()
    // not the file action while connected
    expect(screen.queryByText('Nach DATEV ablegen')).toBeNull()
  })

  it('on + connected + checked out at open: shows the checked-out hint', () => {
    render_({ datevMode: true, connected: true, checkedOutAtOpen: true })
    expect(screen.getByText(/in DATEV ausgecheckt/)).toBeInTheDocument()
  })

  it('on + not connected: shows the file action, fires onFile', () => {
    const h = render_({ datevMode: true, connected: false })
    fireEvent.click(screen.getByText('Nach DATEV ablegen'))
    expect(h.onFile).toHaveBeenCalled()
    expect(screen.queryByText('Nach DATEV zurückschreiben')).toBeNull()
  })

  it('disables the actions while busy', () => {
    render_({ datevMode: true, connected: true, busy: true })
    expect(screen.getByText('Nach DATEV zurückschreiben')).toBeDisabled()
  })
})
