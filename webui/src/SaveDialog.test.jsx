// Component tests for the "embed compression alternatives?" save dialog: the
// three exits (embed / base-only / cancel) map to the right callback values,
// and the document count is surfaced. German source strings (no provider).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { SaveDialog } from './SaveDialog'

afterEach(cleanup)

const renderDialog = (count = 3) => {
  const onChoose = vi.fn()
  const onCancel = vi.fn()
  render(<SaveDialog count={count} onChoose={onChoose} onCancel={onCancel} />)
  return { onChoose, onCancel }
}

describe('SaveDialog', () => {
  it('shows how many documents have alternatives', () => {
    renderDialog(5)
    expect(screen.getByText(/5 Dokument/)).toBeInTheDocument()
  })

  it('"Wie geplant speichern" embeds the alternatives (onChoose(true))', () => {
    const { onChoose } = renderDialog()
    fireEvent.click(screen.getByText('Wie geplant speichern'))
    expect(onChoose).toHaveBeenCalledWith(true)
  })

  it('"Original speichern" keeps only the base version (onChoose(false))', () => {
    const { onChoose } = renderDialog()
    fireEvent.click(screen.getByText('Original speichern'))
    expect(onChoose).toHaveBeenCalledWith(false)
  })

  it('Abbrechen cancels without choosing', () => {
    const { onChoose, onCancel } = renderDialog()
    fireEvent.click(screen.getByText('Abbrechen'))
    expect(onCancel).toHaveBeenCalled()
    expect(onChoose).not.toHaveBeenCalled()
  })

  it('Esc cancels', () => {
    const { onCancel } = renderDialog()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalled()
  })
})
