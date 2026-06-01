// Recursive document-tree view. Click a node to select it (preview); right-click
// for operations via the context menu. Drag a row onto another to move it: top
// quarter = before, bottom = after, middle of a folder = inside. When dropping in
// the "after" gap of a row that is the last child of its folder (i.e. at the
// bottom of a level), a ghost copy of the dragged item is shown at the drop spot;
// slide the cursor left/right to choose the nesting LEVEL (child of the deepest
// folder → … → root). The drop only dispatches a Move/MoveMany — the tree
// re-renders from the core's returned state (no optimistic local mutation).
import { useState } from 'react'

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

function TreeNode({ node, parentId, parentName, index, depth, isLast, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany, levelsFor, drag, setDrag, dragLabel, dragIcon, onDropFiles }) {
  const [over, setOver] = useState(null) // { zone, target, depth, ghost } | null

  const handleDragOver = (e) => {
    if (hasFiles(e)) {
      // OS file import → target the folder under the cursor (a leaf → its parent)
      e.preventDefault()
      e.stopPropagation()
      setOver({ zone: 'fileInto', targetId: node.is_folder ? node.id : parentId,
                targetName: node.is_folder ? node.name : (parentName || 'oberste Ebene') })
      return
    }
    if (!drag || drag === node.id) return
    e.preventDefault()
    e.stopPropagation()
    const zone = dropZone(e, node.is_folder)
    if (zone !== 'after') { setOver({ zone }); return }
    if (isLast) {
      // bottom of a level → choose the nesting level from the cursor's X, show ghost
      const levels = levelsFor(node.id) // deepest → shallowest
      const treeLeft = e.currentTarget.closest('ul.tree').getBoundingClientRect().left
      const maxD = levels[0]?.depth ?? depth
      const minD = levels[levels.length - 1]?.depth ?? depth
      let d = Math.floor((e.clientX - treeLeft) / INDENT)
      d = Math.max(minD, Math.min(maxD, d))
      const target = levels.find((l) => l.depth === d) || levels[0]
      setOver({ zone: 'after', target, depth: d, ghost: true })
    } else {
      setOver({ zone: 'after', target: { parentId, index: index + 1 }, depth, ghost: false })
    }
  }

  const handleDrop = (e) => {
    if (over?.zone === 'fileInto') {
      e.preventDefault()
      e.stopPropagation()
      onDropFiles(e.dataTransfer.files, over.targetId)
      setOver(null)
      return
    }
    if (!drag || drag === node.id || !over) { setOver(null); return }
    e.preventDefault()
    e.stopPropagation()
    const many = selectedIds.includes(drag) && selectedIds.length > 1
    const move = (parent, idx) => (many ? onMoveMany(selectedIds, parent, idx) : onMove(drag, parent, idx))
    if (over.zone === 'into') move(node.id, null)
    else if (over.zone === 'before') move(parentId, index)
    else if (over.zone === 'after') move(over.target.parentId, over.target.index)
    setOver(null)
    setDrag(null)
  }

  const cls = ['row']
  if (selectedIds.includes(node.id)) cls.push('selected')
  if (node.id === primaryId) cls.push('primary')
  if (over && (over.zone === 'before' || over.zone === 'into')) cls.push(`drop-${over.zone}`)
  if (over?.zone === 'after' && !over.ghost) cls.push('drop-after')
  if (over?.zone === 'fileInto') cls.push('file-target')

  return (
    <li>
      <div
        className={cls.join(' ')}
        style={{ paddingLeft: `${depth * INDENT + 6}px` }}
        draggable
        onDragStart={(e) => { e.stopPropagation(); setDrag(node.id); e.dataTransfer.effectAllowed = 'move' }}
        onDragEnd={() => { setDrag(null); setOver(null) }}
        onDragOver={handleDragOver}
        onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(null) }}
        onDrop={handleDrop}
        onClick={(e) => onSelect(node, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey })}
        onContextMenu={(e) => { e.preventDefault(); onContext(e.clientX, e.clientY, node) }}
      >
        <span className={node.is_folder ? 'name folder' : 'name leaf'}>
          {node.is_folder ? '📁' : '📄'} {node.name}
        </span>
        {over?.zone === 'fileInto' && <span className="file-target-badge">→ {over.targetName}</span>}
        {/* ghost preview of where the dragged item will land (bottom drop), at the
            chosen indent level, with the destination named. Absolute → no layout shift. */}
        {over?.zone === 'after' && over.ghost && (
          <div className="drop-ghost" style={{ left: `${over.depth * INDENT + 6}px` }}>
            <span className="drop-ghost-row">{dragIcon} {dragLabel}</span>
            <span className="drop-ghost-where">{over.target.parentName ? `in ${over.target.parentName}` : 'oberste Ebene'}</span>
          </div>
        )}
      </div>
      {node.children?.length > 0 && (
        <ul>
          {node.children.map((c, i, arr) => (
            <TreeNode key={c.id} node={c} parentId={node.id} parentName={node.name} index={i} depth={depth + 1} isLast={i === arr.length - 1}
              selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
              onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag}
              dragLabel={dragLabel} dragIcon={dragIcon} onDropFiles={onDropFiles} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany, levelsFor, onDropFiles }) {
  // `node` is the implicit root container — don't render it; show its children.
  const [drag, setDrag] = useState(null)
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
        <TreeNode key={c.id} node={c} parentId={node.id} parentName={null} index={i} depth={0} isLast={i === arr.length - 1}
          selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
          onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag}
          dragLabel={dragLabel} dragIcon={dragIcon} onDropFiles={onDropFiles} />
      ))}
    </ul>
  )
}
