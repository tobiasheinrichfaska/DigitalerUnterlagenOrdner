// Save split-button (#3): the main part saves in place; a caret opens a small
// dropdown menu with "Speichern unter…". Replaces the two separate Save / Save-as
// toolbar buttons. Accessible: the caret has aria-haspopup/aria-expanded, the
// dropdown is role=menu with a role=menuitem; it closes on Escape and on an
// outside click, and focus moves to the menu item when it opens.
import { useEffect, useRef, useState } from 'react'
import { useT } from './i18n/LanguageProvider'

export function SaveSplitButton({ onSave, onSaveAs, dirty = false }) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const itemRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const onDocDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDocDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDocDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  // Move focus into the menu when it opens (so keyboard users land on the action).
  useEffect(() => { if (open) itemRef.current?.focus() }, [open])

  const chooseSaveAs = () => { setOpen(false); onSaveAs() }

  return (
    <span className="save-split" ref={wrapRef}>
      <button className="save-main" onClick={onSave}>💾 {t('Speichern')}{dirty ? ' •' : ''}</button>
      <button className="save-caret" aria-haspopup="menu" aria-expanded={open}
        title={t('Weitere Speicheroptionen')} aria-label={t('Weitere Speicheroptionen')}
        onClick={() => setOpen((o) => !o)}>▾</button>
      {open && (
        <div className="save-menu" role="menu">
          <button ref={itemRef} role="menuitem" className="save-menu-item" onClick={chooseSaveAs}>
            {t('Speichern unter…')}
          </button>
        </div>
      )}
    </span>
  )
}
