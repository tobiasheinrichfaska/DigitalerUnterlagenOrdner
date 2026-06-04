// Recursive document-tree view. Click a node to select it (preview); right-click
// for operations via the context menu. Drag a row onto another to move it: top
// quarter = before, bottom = after, middle of a folder = inside. When dropping in
// the "after" gap of a row that is the last child of its folder (i.e. at the
// bottom of a level), a ghost copy of the dragged item is shown at the drop spot;
// slide the cursor left/right to choose the nesting LEVEL (child of the deepest
// folder → … → root). The drop only dispatches a Move/MoveMany — the tree
// re-renders from the core's returned state (no optimistic local mutation).
import { useRef, useState } from 'react'
import { useT } from './i18n/LanguageProvider'

const INDENT = 18 // px per nesting level (matches ul padding-left)

function findNode(n, id) {
  if (n.id === id) return n
  for (const c of n.children ?? []) {
    const r = findNode(c, id)
    if (r) return r
  }
  return null
}

const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files')

// optimistic placeholder shown while a dropped file is being imported (a sliding
// progress shimmer on the node itself, replaced by the real node when done). It is
// NOT a valid drop target — dragging over it shows the no-drop cursor (not calling
// preventDefault on dragover) so nothing can be inserted relative to an in-flight
// import; stopPropagation keeps the parent list from accepting it instead.
function PendingRow({ name, depth }) {
  return (
    <li>
      <div className="row pending" style={{ paddingLeft: `${depth * INDENT + 6}px` }}
        onDragOver={(e) => e.stopPropagation()}
        onDrop={(e) => { e.preventDefault(); e.stopPropagation() }}>
        <span className="tw-chevron" />
        <span className="name leaf">📄 {name}</span>
      </div>
    </li>
  )
}

function dropZone(e, isFolder) {
  const r = e.currentTarget.getBoundingClientRect()
  const y = e.clientY - r.top
  if (isFolder) {
    if (y < r.height * 0.25) return 'before'
    if (y > r.height * 0.75) return 'after'
    return 'into'
  }
  return y < r.height / 2 ? 'before' : 'after'
}

function TreeNode({ node, parentId, index, depth, isLast, selectedIds, primaryId, grabbedId, forceExpand, editing, setEditing, onRename, renameTimerRef, onToggleCollapse, onSelect, onContext, onMove, onMoveMany, levelsFor, drag, setDrag, dragLabel, dragIcon, onDropFiles, pending }) {
  const [over, setOver] = useState(null) // { zone, target, depth, ghost } | null
  const { t } = useT()

  const handleDragOver = (e) => {
    const files = hasFiles(e)
    if (!files && (!drag || drag === node.id)) return
    e.preventDefault()
    e.stopPropagation()
    const zone = dropZone(e, node.is_folder)
    if (zone !== 'after') { setOver({ zone, files }); return }
    if (isLast) {
      // bottom of a level → choose the nesting level from the cursor's X, show ghost
      const levels = levelsFor(node.id) // deepest → shallowest
      const treeLeft = e.currentTarget.closest('ul.tree').getBoundingClientRect().left
      const maxD = levels[0]?.depth ?? depth
      const minD = levels[levels.length - 1]?.depth ?? depth
      let d = Math.floor((e.clientX - treeLeft) / INDENT)
      d = Math.max(minD, Math.min(maxD, d))
      const target = levels.find((l) => l.depth === d) || levels[0]
      setOver({ zone: 'after', target, depth: d, ghost: true, files })
    } else {
      setOver({ zone: 'after', target: { parentId, index: index + 1 }, depth, ghost: false, files })
    }
  }

  const handleDrop = (e) => {
    if (!over) { setOver(null); return }
    const isFile = over.files
    if (!isFile && (!drag || drag === node.id)) { setOver(null); return }
    e.preventDefault()
    e.stopPropagation()
    const files = isFile ? Array.from(e.dataTransfer.files) : null
    const many = !isFile && selectedIds.includes(drag) && selectedIds.length > 1
    const place = (parent, idx) => {
      if (isFile) onDropFiles(files, parent, idx)
      else if (many) onMoveMany(selectedIds, parent, idx)
      else onMove(drag, parent, idx)
    }
    if (over.zone === 'into') place(node.id, null)
    else if (over.zone === 'before') place(parentId, index)
    else if (over.zone === 'after') place(over.target.parentId, over.target.index)
    setOver(null)
    setDrag(null)
  }

  const cls = ['row']
  if (selectedIds.includes(node.id)) cls.push('selected')
  if (node.id === primaryId) cls.push('primary')
  if (node.id === grabbedId) cls.push('grabbed')
  if (over && (over.zone === 'before' || over.zone === 'into')) cls.push(`drop-${over.zone}`)
  if (over?.zone === 'after' && !over.ghost) cls.push('drop-after')

  return (
    <li>
      <div
        className={cls.join(' ')}
        style={{ paddingLeft: `${depth * INDENT + 6}px` }}
        draggable={editing !== node.id}
        onDragStart={(e) => { e.stopPropagation(); setDrag(node.id); e.dataTransfer.effectAllowed = 'move' }}
        onDragEnd={() => { setDrag(null); setOver(null) }}
        onDragOver={handleDragOver}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(null) }}
        onDrop={handleDrop}
        onClick={(e) => {
          const mods = { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey }
          clearTimeout(renameTimerRef.current)
          // click an already-selected (marked) node again → inline rename (Explorer-style);
          // a double-click cancels the pending rename.
          if (!mods.ctrl && !mods.shift && node.id === primaryId) {
            renameTimerRef.current = setTimeout(() => setEditing(node.id), 350)
          } else onSelect(node, mods)
        }}
        onDoubleClick={() => clearTimeout(renameTimerRef.current)}
        onContextMenu={(e) => { e.preventDefault(); onContext(e.clientX, e.clientY, node) }}
      >
        {node.is_folder ? (
          <button className="tw-chevron" title={node.collapsed ? t('Aufklappen') : t('Zuklappen')}
            onClick={(e) => { e.stopPropagation(); onToggleCollapse(node.id) }}>
            {node.collapsed ? '▸' : '▾'}
          </button>
        ) : <span className="tw-chevron" />}
        {editing === node.id ? (
          <input className="rename-input" defaultValue={node.name} autoFocus
            onFocus={(e) => e.target.select()}
            onClick={(e) => e.stopPropagation()}
            onMouseDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation()
              if (e.key === 'Enter') { onRename(node.id, e.target.value); setEditing(null) }
              else if (e.key === 'Escape') setEditing(null)
            }}
            onBlur={(e) => { onRename(node.id, e.target.value); setEditing(null) }}
          />
        ) : (
          <span className={node.is_folder ? 'name folder' : 'name leaf'}>
            {node.is_folder ? '📁' : '📄'} {node.name}
          </span>
        )}
        {node.tags?.length > 0 && (
          <span className="tw-tags">
            {node.tags.map((tg) => <span key={tg} className="tw-tag">{tg}</span>)}
          </span>
        )}
        {/* ghost preview of where the dragged item will land (bottom drop), at the
            chosen indent level, with the destination named. Absolute → no layout shift. */}
        {over?.zone === 'after' && over.ghost && (
          <div className="drop-ghost" style={{ left: `${over.depth * INDENT + 6}px` }}>
            <span className="drop-ghost-row">{over.files ? '📥 importieren' : `${dragIcon} ${dragLabel}`}</span>
            <span className="drop-ghost-where">{over.target.parentName ? `in ${over.target.parentName}` : 'oberste Ebene'}</span>
          </div>
        )}
      </div>
      {(forceExpand || !node.collapsed) && (node.children?.length > 0 || pending.some((p) => p.parentId === node.id)) && (
        <ul>
          {node.children?.map((c, i, arr) => (
            <TreeNode key={c.id} node={c} parentId={node.id} index={i} depth={depth + 1} isLast={i === arr.length - 1}
              selectedIds={selectedIds} primaryId={primaryId} grabbedId={grabbedId} forceExpand={forceExpand}
              editing={editing} setEditing={setEditing} onRename={onRename} renameTimerRef={renameTimerRef} onToggleCollapse={onToggleCollapse}
              onSelect={onSelect} onContext={onContext}
              onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag}
              dragLabel={dragLabel} dragIcon={dragIcon} onDropFiles={onDropFiles} pending={pending} />
          ))}
          {pending.filter((p) => p.parentId === node.id).map((p) => (
            <PendingRow key={p.key} name={p.name} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, selectedIds, primaryId, grabbedId, forceExpand, onToggleCollapse, onSelect, onContext, onMove, onMoveMany, levelsFor, onRename, onDropFiles, pending = [] }) {
  // `node` is the implicit root container — don't render it; show its children.
  const [drag, setDrag] = useState(null)
  const [editing, setEditing] = useState(null) // node id being inline-renamed
  const renameTimerRef = useRef(0) // shared: click-marked-again schedules a rename
  const many = drag && selectedIds.includes(drag) && selectedIds.length > 1
  const dragNode = drag ? findNode(node, drag) : null
  const dragLabel = many ? `${selectedIds.length} Elemente` : (dragNode?.name ?? '')
  const dragIcon = many ? '🗂' : (dragNode?.is_folder ? '📁' : '📄')

  const dropOnRoot = (e) => {
    if (hasFiles(e)) { e.preventDefault(); onDropFiles(e.dataTransfer.files, node.id); return } // empty area → root
    if (!drag) return
    e.preventDefault()
    if (many) onMoveMany(selectedIds, node.id, null)
    else onMove(drag, node.id, null)
    setDrag(null)
  }
  return (
    <ul className="tree" onDragOver={(e) => { if (drag || hasFiles(e)) e.preventDefault() }} onDrop={dropOnRoot}>
      {(node.children ?? []).map((c, i, arr) => (
        <TreeNode key={c.id} node={c} parentId={node.id} index={i} depth={0} isLast={i === arr.length - 1}
          selectedIds={selectedIds} primaryId={primaryId} grabbedId={grabbedId} forceExpand={forceExpand}
          editing={editing} setEditing={setEditing} onRename={onRename} renameTimerRef={renameTimerRef} onToggleCollapse={onToggleCollapse}
          onSelect={onSelect} onContext={onContext}
          onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag}
          dragLabel={dragLabel} dragIcon={dragIcon} onDropFiles={onDropFiles} pending={pending} />
      ))}
      {pending.filter((p) => p.parentId === node.id).map((p) => (
        <PendingRow key={p.key} name={p.name} depth={0} />
      ))}
    </ul>
  )
}
