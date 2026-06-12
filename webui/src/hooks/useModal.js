// Shared focus-management hook for modal dialogs.
//
// On mount:
//   - Focuses the first focusable element inside the dialog (or a supplied ref).
//   - Traps Tab within the dialog (Shift+Tab wraps from first → last, Tab wraps last → first).
//   - Closes on Escape by calling onClose().
//   - Restores focus to the element that was active before the dialog opened.
//
// Usage:
//   const dialogRef = useModal({ onClose })
//   return <div ref={dialogRef} role="dialog" aria-modal="true"> … </div>
import { useEffect, useRef } from 'react'

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'textarea:not([disabled])',
  'input:not([disabled])', 'select:not([disabled])', '[tabindex]:not([tabindex="-1"])',
].join(', ')

export function useModal({ onClose }) {
  const dialogRef = useRef(null)
  const previousFocus = useRef(null)

  useEffect(() => {
    // Remember who had focus before the dialog opened so we can restore it on unmount.
    previousFocus.current = document.activeElement

    const el = dialogRef.current
    if (!el) return

    // Focus the first focusable element in the dialog.
    const focusables = () => Array.from(el.querySelectorAll(FOCUSABLE))
    const first = focusables()[0]
    if (first) first.focus()

    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const items = focusables()
      if (!items.length) { e.preventDefault(); return }
      const firstItem = items[0]
      const lastItem = items[items.length - 1]
      if (e.shiftKey) {
        if (document.activeElement === firstItem) { e.preventDefault(); lastItem.focus() }
      } else {
        if (document.activeElement === lastItem) { e.preventDefault(); firstItem.focus() }
      }
    }

    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      // Restore focus to whoever had it before the dialog opened.
      if (previousFocus.current && typeof previousFocus.current.focus === 'function') {
        previousFocus.current.focus()
      }
    }
  }, [onClose])

  return dialogRef
}
