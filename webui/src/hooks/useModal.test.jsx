// Tests for useModal: focus-on-open, Tab trap, Esc-closes, focus-restore.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { useModal } from './useModal'

// Minimal dialog fixture that uses the hook
function TestDialog({ onClose }) {
  const ref = useModal({ onClose })
  return (
    <div ref={ref} role="dialog" aria-modal="true" data-testid="dialog">
      <button data-testid="btn1">First</button>
      <button data-testid="btn2">Second</button>
      <button data-testid="btn3">Third</button>
    </div>
  )
}

afterEach(() => { vi.restoreAllMocks() })

describe('useModal — focus on open', () => {
  it('focuses the first focusable element when mounted', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)
    expect(document.activeElement).toBe(screen.getByTestId('btn1'))
  })
})

describe('useModal — Esc closes', () => {
  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('useModal — Tab trap', () => {
  it('Tab on the last button wraps to the first', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)
    screen.getByTestId('btn3').focus()
    expect(document.activeElement).toBe(screen.getByTestId('btn3'))
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: false })
    expect(document.activeElement).toBe(screen.getByTestId('btn1'))
  })

  it('Shift+Tab on the first button wraps to the last', () => {
    const onClose = vi.fn()
    render(<TestDialog onClose={onClose} />)
    screen.getByTestId('btn1').focus()
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByTestId('btn3'))
  })
})

describe('useModal — focus restore on unmount', () => {
  it('restores focus to the element that had it before the dialog opened', () => {
    const onClose = vi.fn()
    // Create an element outside the dialog that holds focus
    const trigger = document.createElement('button')
    trigger.textContent = 'Open'
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    const { unmount } = render(<TestDialog onClose={onClose} />)
    // Dialog took focus away from trigger
    expect(document.activeElement).toBe(screen.getByTestId('btn1'))

    // Unmount → focus should return to the trigger
    unmount()
    expect(document.activeElement).toBe(trigger)
    document.body.removeChild(trigger)
  })
})

describe('ExportDialog — uses useModal (smoke)', () => {
  it('Esc calls onCancel', async () => {
    const { ExportDialog } = await import('../ExportDialog')
    const onCancel = vi.fn()
    render(<ExportDialog hasTags={false} onChoose={vi.fn()} onCancel={onCancel} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalled()
  })
})
