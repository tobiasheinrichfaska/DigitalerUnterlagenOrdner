// SaveSplitButton (#3): main part saves in place; the caret opens a dropdown with
// "Speichern unter…". Accessible: aria-expanded, role=menu/menuitem, Escape +
// outside-click close. German source strings (no LanguageProvider).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { SaveSplitButton } from './SaveSplitButton'

const setup = (props = {}) => {
  const onSave = vi.fn()
  const onSaveAs = vi.fn()
  const { container } = render(<SaveSplitButton onSave={onSave} onSaveAs={onSaveAs} dirty={false} {...props} />)
  return { container, onSave, onSaveAs }
}
const caret = () => screen.getByLabelText('Weitere Speicheroptionen')

beforeEach(() => { vi.restoreAllMocks() })
afterEach(cleanup)

describe('SaveSplitButton (#3)', () => {
  it('the main part saves in place', () => {
    const { container, onSave } = setup()
    fireEvent.click(container.querySelector('.save-main'))
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  it('shows the dirty marker on the main part', () => {
    const { container } = setup({ dirty: true })
    expect(container.querySelector('.save-main').textContent).toContain('•')
  })

  it('the caret opens a menu containing Speichern unter…', () => {
    setup()
    expect(screen.queryByRole('menu')).toBeNull()
    fireEvent.click(caret())
    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Speichern unter/ })).toBeInTheDocument()
  })

  it('choosing Speichern unter… calls onSaveAs and closes the menu', () => {
    const { onSaveAs } = setup()
    fireEvent.click(caret())
    fireEvent.click(screen.getByRole('menuitem', { name: /Speichern unter/ }))
    expect(onSaveAs).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('the caret reflects aria-expanded', () => {
    setup()
    expect(caret()).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(caret())
    expect(caret()).toHaveAttribute('aria-expanded', 'true')
  })

  it('Escape closes the menu', () => {
    setup()
    fireEvent.click(caret())
    expect(screen.getByRole('menu')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('a click outside closes the menu', () => {
    setup()
    fireEvent.click(caret())
    expect(screen.getByRole('menu')).toBeInTheDocument()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('menu')).toBeNull()
  })

  it('does not call onSaveAs just by opening the menu', () => {
    const { onSaveAs } = setup()
    fireEvent.click(caret())
    expect(onSaveAs).not.toHaveBeenCalled()
  })
})
