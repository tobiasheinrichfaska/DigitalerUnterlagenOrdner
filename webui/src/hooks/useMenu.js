// Shared accessible-menu behaviour, factored out of ContextMenu and SaveSplitButton
// so the keyboard/a11y contract lives in one place (#10):
//   • rovingFocusKeydown — ↑/↓ cycle the menu's <button>s, Home/End jump to the ends.
//   • tagMenuItems       — mark every <button> inside the menu as role="menuitem".
//   • useMenuDismiss     — close on Escape and on an outside mousedown while open.
// Enter/Space activate the focused <button> natively, so they need no handling here.
import { useEffect } from 'react'

export function rovingFocusKeydown(container, e) {
  const btns = Array.from(container?.querySelectorAll('button') ?? [])
  if (!btns.length) return
  const i = btns.indexOf(document.activeElement)
  if (e.key === 'ArrowDown') { e.preventDefault(); btns[i < 0 ? 0 : (i + 1) % btns.length].focus() }
  else if (e.key === 'ArrowUp') { e.preventDefault(); btns[i < 0 ? btns.length - 1 : (i - 1 + btns.length) % btns.length].focus() }
  else if (e.key === 'Home') { e.preventDefault(); btns[0].focus() }
  else if (e.key === 'End') { e.preventDefault(); btns[btns.length - 1].focus() }
}

export function tagMenuItems(container) {
  container?.querySelectorAll('button').forEach((b) => b.setAttribute('role', 'menuitem'))
}

// Close the menu on Escape or on a mousedown outside `ref` — but only while `open`.
export function useMenuDismiss(ref, open, onClose) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onDown)
    }
  }, [ref, open, onClose])
}
