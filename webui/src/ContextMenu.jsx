// Right-click context menu for a tree node — operations live here (like the old
// app's tree context menu), not as buttons.
import { useState, useLayoutEffect, useEffect, useRef } from 'react'
import { useT } from './i18n/LanguageProvider'
import { rovingFocusKeydown, tagMenuItems } from './hooks/useMenu'

// The status DATA keys (from config().statuses) → their German display text, which
// t() then translates. Keys stay erfasst/zu erfassen/vorjahreswert (persisted data).
const STATUS_DE = { '': 'Kein Status', erfasst: 'Erfasst', 'zu erfassen': 'Zu erfassen', vorjahreswert: 'Vorjahr' }
const statusLabel = (t, key) => t(STATUS_DE[key] ?? key)  // internal helper; not exported (keeps fast-refresh happy)

export function ContextMenu({ menu, dispatch, onClose, mergeIds, group, onExport, onDelete, onGroup, onOpenInPdfTool, selectedIds, onSetCollapsed, onExpandAll, onCollapseAll, statuses = [], editLocked = false }) {
  const { t } = useT()
  const [splitOpen, setSplitOpen] = useState(false)
  const menuRef = useRef(null)
  const [pos, setPos] = useState(null)  // null until measured → render at cursor first
  const { x, y, node } = menu ?? {}
  // clamp the menu into the viewport so a right-click near the bottom/right edge
  // isn't cut off (flip up / pull left to fit). useLayoutEffect runs pre-paint.
  useLayoutEffect(() => {
    const el = menuRef.current
    if (!el) { setPos(null); return }
    const { width, height } = el.getBoundingClientRect()
    setPos({
      left: Math.max(4, Math.min(x, window.innerWidth - width - 4)),
      top: Math.max(4, Math.min(y, window.innerHeight - height - 4)),
    })
    // Reset the split flyout whenever the menu target changes
    setSplitOpen(false)
    // a11y (F-3): tag items as menuitems and move focus into the menu so it's
    // immediately keyboard-operable (focus-first-on-open). Shared helper (#10).
    tagMenuItems(el)
    el.querySelector('button')?.focus()
  }, [menu, x, y])

  // Escape closes the menu (mirrors the backdrop click; makes the CLAUDE.md
  // "closes on Esc" claim true — F3).
  useEffect(() => {
    if (!menu) return undefined
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menu, onClose])

  // Keep role="menuitem" on items that appear after the initial open (the split
  // flyout submenu) so arrow navigation and screen readers reach them too (F-3).
  useEffect(() => { tagMenuItems(menuRef.current) }, [splitOpen])

  if (!menu) return null

  const splitN = (intoFolder) => {
    const s = window.prompt(t('Seiten pro Knoten:'), '10')
    const n = parseInt(s, 10)
    if (n >= 1) run({ type: 'SplitInto', size: n, into_folder: intoFolder })
    else onClose()
  }
  // export the current selection if this node is part of it, else just this node
  const exportIds = (selectedIds?.includes(node.id) && selectedIds.length >= 1) ? selectedIds : [node.id]
  // merge + group act on the SELECTION — offer them only when the clicked node is part
  // of it (same membership rule as export/status/delete above/below)
  const inSelection = selectedIds?.includes(node.id)
  const mergeHere = mergeIds && inSelection ? mergeIds : null
  const groupHere = group && inSelection ? group : null
  const isLeaf = !node.is_folder
  const run = (extra) => {
    dispatch({ ...extra, node_id: node.id })
    onClose()
  }
  const merge = () => {
    dispatch({ type: 'Merge', node_ids: mergeIds })
    onClose()
  }
  const groupInto = () => {
    const name = window.prompt(t('Name des neuen Ordners'), t('Neue Gruppe'))
    if (name) {
      // App resolves folder/child overlaps; fall back to a direct dispatch if not wired
      if (onGroup) onGroup(name)
      else dispatch({ type: 'GroupIntoFolder', node_ids: group.ids, parent_id: group.parentId, name, new_id: null, index: null })
    }
    onClose()
  }

  const rename = () => {
    const raw = window.prompt(t('Neuer Name'), node.name)
    // Apply the same trim + no-change guard as the inline rename in Tree.jsx / App.jsx:
    // null = cancelled, empty/whitespace = ignored, same name = no-op.
    const name = raw != null ? raw.trim() : null
    if (name && name !== node.name) run({ type: 'Rename', name })
    else onClose()
  }
  const addFolder = () => {
    dispatch({ type: 'AddFolder', parent_id: node.id, name: t('Neuer Ordner'), index: null, new_id: null })
    onClose()
  }

  // Roving focus: ↑/↓ cycle the items, Home/End jump to the ends. Enter/Space
  // activate the focused <button> natively; Esc closes via the window listener (F-3).
  // Shared helper (#10).
  const onMenuKey = (e) => rovingFocusKeydown(menuRef.current, e)

  return (
    <>
      <div
        className="cm-backdrop"
        onClick={onClose}
        onContextMenu={(e) => { e.preventDefault(); onClose() }}
      />
      <div ref={menuRef} className="context-menu" role="menu" aria-label={t('Kontextmenü')}
        tabIndex={-1} onKeyDown={onMenuKey}
        style={{ left: pos ? pos.left : x, top: pos ? pos.top : y }}>
        {!editLocked && (mergeHere || groupHere) && (
          <>
            {mergeHere && <button onClick={merge}>{t('Zusammenführen → 1 PDF ({count})', { count: mergeHere.length })}</button>}
            {groupHere && <button onClick={groupInto}>{t('In neuen Ordner ({count})', { count: groupHere.ids.length })}</button>}
            <div className="cm-sep" />
          </>
        )}
        <button onClick={rename}>{t('Umbenennen')}</button>
        {!editLocked && isLeaf && onOpenInPdfTool && (
          <button onClick={() => { onOpenInPdfTool(node); onClose() }}>{t('Im PDF-Tool öffnen')}</button>
        )}
        {!editLocked && isLeaf && node.pdf_length > 1 && (
          <div className="cm-haschild" onMouseEnter={() => setSplitOpen(true)} onMouseLeave={() => setSplitOpen(false)}>
            <button className="cm-trigger" onClick={() => setSplitOpen((v) => !v)}>
              {t('Splitten')}<span className="cm-arrow">▸</span>
            </button>
            {splitOpen && (
              <div className="context-menu cm-flyout">
                <button onClick={() => run({ type: 'Split' })}>{t('pro Seite')}</button>
                <button onClick={() => splitN(false)}>{t('N Seiten pro Knoten…')}</button>
                <button onClick={() => run({ type: 'SplitInto', size: 1, into_folder: true })}>{t('pro Seite → neuer Ordner')}</button>
                <button onClick={() => splitN(true)}>{t('N Seiten → neuer Ordner…')}</button>
              </div>
            )}
          </div>
        )}
        {!editLocked && node.is_folder && <button onClick={addFolder}>{t('Ordner anlegen')}</button>}
        {node.is_folder && (
          <button onClick={() => { onSetCollapsed(node.id, !node.collapsed); onClose() }}>
            {node.collapsed ? t('Aufklappen') : t('Zuklappen')}
          </button>
        )}
        <button onClick={() => { onExpandAll(); onClose() }}>{t('Alle aufklappen')}</button>
        <button onClick={() => { onCollapseAll(); onClose() }}>{t('Alle zuklappen')}</button>
        <div className="cm-sep" />
        {(() => {
          const multi = selectedIds?.includes(node.id) && selectedIds.length > 1
          const setStatus = (key) => {
            if (multi) { dispatch({ type: 'SetStatusMany', node_ids: selectedIds, status: key }); onClose() }
            else run({ type: 'SetStatus', status: key })
          }
          return (
            <>
              <div className="cm-label">
                {multi ? t('Status ({count})', { count: selectedIds.length })
                  : node.is_folder ? t('Status (gesamter Inhalt)') : t('Status')}
              </div>
              {statuses.map((key) => (
                <button key={key} className={!multi && !node.is_folder && node.status === key ? 'active' : ''}
                  onClick={() => setStatus(key)}>
                  {statusLabel(t, key)}
                </button>
              ))}
            </>
          )
        })()}
        <div className="cm-sep" />
        <button onClick={() => { onExport(exportIds); onClose() }}>
          {exportIds.length > 1 ? t('Auswahl als PDF exportieren ({count})', { count: exportIds.length }) : t('Als PDF exportieren')}
        </button>
        {!editLocked && (
          <>
            <div className="cm-sep" />
            <button className="danger" onClick={() => {
              if (onDelete && selectedIds?.includes(node.id) && selectedIds.length > 1) { onDelete(); onClose() }
              else run({ type: 'Delete' })
            }}>{t('Löschen')}{selectedIds?.includes(node.id) && selectedIds.length > 1 ? ` (${selectedIds.length})` : ''}</button>
          </>
        )}
      </div>
    </>
  )
}
