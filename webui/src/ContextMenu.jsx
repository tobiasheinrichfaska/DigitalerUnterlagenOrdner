// Right-click context menu for a tree node — operations live here (like the old
// app's tree context menu), not as buttons.

const STATUSES = [
  ['erfasst', 'Erfasst'],
  ['zu erfassen', 'Zu erfassen'],
  ['vorjahreswert', 'Vorjahr'],
]

export function ContextMenu({ menu, dispatch, onClose, mergeIds, group, onExport, selectedIds }) {
  if (!menu) return null
  const { x, y, node } = menu
  // export the multi-selection if this node is part of one (2+), else just this node
  const exportIds = (selectedIds?.includes(node.id) && selectedIds.length >= 2) ? selectedIds : [node.id]
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
    const name = window.prompt('Name des neuen Ordners', 'Neue Gruppe')
    if (name) dispatch({ type: 'GroupIntoFolder', node_ids: group.ids, parent_id: group.parentId, name, new_id: null, index: null })
    onClose()
  }

  const rename = () => {
    const name = window.prompt('Neuer Name', node.name)
    if (name) run({ type: 'Rename', name })
    else onClose()
  }
  const addFolder = () => {
    dispatch({ type: 'AddFolder', parent_id: node.id, name: 'Neuer Ordner', index: null, new_id: null })
    onClose()
  }

  return (
    <>
      <div
        className="cm-backdrop"
        onClick={onClose}
        onContextMenu={(e) => { e.preventDefault(); onClose() }}
      />
      <div className="context-menu" style={{ left: x, top: y }}>
        {(mergeIds || group) && (
          <>
            {mergeIds && <button onClick={merge}>Zusammenführen → 1 PDF ({mergeIds.length})</button>}
            {group && <button onClick={groupInto}>In neuen Ordner ({group.ids.length})</button>}
            <div className="cm-sep" />
          </>
        )}
        <button onClick={rename}>Umbenennen</button>
        {isLeaf && node.pdf_length > 1 && <button onClick={() => run({ type: 'Split' })}>Splitten</button>}
        {node.is_folder && <button onClick={addFolder}>Ordner anlegen</button>}
        <div className="cm-sep" />
        <div className="cm-label">Status</div>
        {STATUSES.map(([key, label]) => (
          <button key={key} className={node.status === key ? 'active' : ''} onClick={() => run({ type: 'SetStatus', status: key })}>
            {label}
          </button>
        ))}
        <div className="cm-sep" />
        <button onClick={() => { onExport(exportIds); onClose() }}>
          {exportIds.length > 1 ? `Auswahl als PDF exportieren (${exportIds.length})` : 'Als PDF exportieren'}
        </button>
        <div className="cm-sep" />
        <button className="danger" onClick={() => run({ type: 'Delete' })}>Löschen</button>
      </div>
    </>
  )
}
