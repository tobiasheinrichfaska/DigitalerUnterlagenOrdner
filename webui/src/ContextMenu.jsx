// Right-click context menu for a tree node — operations live here (like the old
// app's tree context menu), not as buttons.
import { useState, useLayoutEffect, useRef } from 'react'
import { useT } from './i18n/LanguageProvider'

// The status DATA keys (from config().statuses) → their German display text, which
// t() then translates. Keys stay erfasst/zu erfassen/vorjahreswert (persisted data).
const STATUS_DE = { erfasst: 'Erfasst', 'zu erfassen': 'Zu erfassen', vorjahreswert: 'Vorjahr' }
export const statusLabel = (t, key) => t(STATUS_DE[key] ?? key)

export function ContextMenu({ menu, dispatch, onClose, mergeIds, group, onExport, onDelete, onGroup, selectedIds, onSetCollapsed, onExpandAll, onCollapseAll, statuses = [] }) {
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
  }, [menu, x, y])
  if (!menu) return null

  const splitN = (intoFolder) => {
    const s = window.prompt(t('Seiten pro Knoten:'), '10')
    const n = parseInt(s, 10)
    if (n >= 1) run({ type: 'SplitInto', size: n, into_folder: intoFolder })
    else onClose()
  }
  // export the current selection if this node is part of it, else just this node
  const exportIds = (selectedIds?.includes(node.id) && selectedIds.length >= 1) ? selectedIds : [node.id]
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
    const name = window.prompt(t('Neuer Name'), node.name)
    if (name) run({ type: 'Rename', name })
    else onClose()
  }
  const addFolder = () => {
    dispatch({ type: 'AddFolder', parent_id: node.id, name: t('Neuer Ordner'), index: null, new_id: null })
    onClose()
  }

  return (
    <>
      <div
        className="cm-backdrop"
        onClick={onClose}
        onContextMenu={(e) => { e.preventDefault(); onClose() }}
      />
      <div ref={menuRef} className="context-menu"
        style={{ left: pos ? pos.left : x, top: pos ? pos.top : y }}>
        {(mergeIds || group) && (
          <>
            {mergeIds && <button onClick={merge}>{t('Zusammenführen → 1 PDF ({count})', { count: mergeIds.length })}</button>}
            {group && <button onClick={groupInto}>{t('In neuen Ordner ({count})', { count: group.ids.length })}</button>}
            <div className="cm-sep" />
          </>
        )}
        <button onClick={rename}>{t('Umbenennen')}</button>
        {isLeaf && node.pdf_length > 1 && (
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
        {node.is_folder && <button onClick={addFolder}>{t('Ordner anlegen')}</button>}
        {node.is_folder && (
          <button onClick={() => { onSetCollapsed(node.id, !node.collapsed); onClose() }}>
            {node.collapsed ? t('Aufklappen') : t('Zuklappen')}
          </button>
        )}
        <button onClick={() => { onExpandAll(); onClose() }}>{t('Alle aufklappen')}</button>
        <button onClick={() => { onCollapseAll(); onClose() }}>{t('Alle zuklappen')}</button>
        <div className="cm-sep" />
        <div className="cm-label">{t('Status')}</div>
        {statuses.map((key) => (
          <button key={key} className={node.status === key ? 'active' : ''} onClick={() => run({ type: 'SetStatus', status: key })}>
            {statusLabel(t, key)}
          </button>
        ))}
        <div className="cm-sep" />
        <button onClick={() => { onExport(exportIds); onClose() }}>
          {exportIds.length > 1 ? t('Auswahl als PDF exportieren ({count})', { count: exportIds.length }) : t('Als PDF exportieren')}
        </button>
        <div className="cm-sep" />
        <button className="danger" onClick={() => {
          if (onDelete && selectedIds?.includes(node.id) && selectedIds.length > 1) { onDelete(); onClose() }
          else run({ type: 'Delete' })
        }}>{t('Löschen')}{selectedIds?.includes(node.id) && selectedIds.length > 1 ? ` (${selectedIds.length})` : ''}</button>
      </div>
    </>
  )
}
