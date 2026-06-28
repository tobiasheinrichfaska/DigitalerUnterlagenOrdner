// Save split-button (#3): the main part saves in place; a caret opens a small
// dropdown menu with "Speichern unter…". Replaces the two separate Save / Save-as
// toolbar buttons. Accessible: the caret has aria-haspopup/aria-expanded, the
// dropdown is role=menu with a role=menuitem; it closes on Escape and on an
// outside click, and focus moves to the menu item when it opens.
import { useEffect, useRef, useState } from 'react'
import { useT } from './i18n/LanguageProvider'
import { useMenuDismiss, rovingFocusKeydown } from './hooks/useMenu'

export function SaveSplitButton({ onSave, onSaveAs, dirty = false }) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const itemRef = useRef(null)

  // Shared close-on-Escape / outside-click (#10).
  useMenuDismiss(wrapRef, open, () => setOpen(false))

  // Move focus into the menu when it opens (so keyboard users land on the action).
  useEffect(() => { if (open) itemRef.current?.focus() }, [open])

  const chooseSaveAs = () => { setOpen(false); onSaveAs() }

  return (
    <span className="save-split" ref={wrapRef}>
      <button className="save-main tb-btn" onClick={onSave} title={t('Speichern')} aria-label={t('Speichern')}>
        💾{dirty ? <span className="dirty-dot" aria-hidden="true">•</span> : ''}
      </button>
      <button className="save-caret" aria-haspopup="menu" aria-expanded={open}
        title={t('Weitere Speicheroptionen')} aria-label={t('Weitere Speicheroptionen')}
        onClick={() => setOpen((o) => !o)}>▾</button>
      {open && (
        <div className="save-menu" role="menu" onKeyDown={(e) => rovingFocusKeydown(e.currentTarget, e)}>
          <button ref={itemRef} role="menuitem" className="save-menu-item" onClick={chooseSaveAs}>
            {t('Speichern unter…')}
          </button>
        </div>
      )}
    </span>
  )
}
