// Recursive document-tree view. Click a node to select it (preview); right-click
// for operations (rename, split, status, folders, delete) via the context menu.
// Drag a row onto another to move it: top quarter = before, bottom = after,
// middle of a folder = inside. When dropping in the "after" gap of a row that is
// the last child of its folder, slide the cursor left/right to choose the nesting
// LEVEL (child of the deepest folder → … → root); a guide line shows where it
// lands. The drop only dispatches a Move/MoveMany — the tree re-renders from the
// core's returned state (no optimistic local mutation).
import { useState } from 'react'

const INDENT = 18 // px per nesting level (matches ul padding-left)

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

function TreeNode({ node, parentId, index, depth, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany, levelsFor, drag, setDrag }) {
  const [over, setOver] = useState(null) // { zone, target?, depth? } | null

  const handleDragOver = (e) => {
    if (!drag || drag === node.id) return
    e.preventDefault()
    e.stopPropagation()
    const zone = dropZone(e, node.is_folder)
    if (zone === 'after') {
      // choose the nesting level from the cursor's horizontal position
      const levels = levelsFor(node.id) // deepest → shallowest
      const treeLeft = e.currentTarget.closest('ul.tree').getBoundingClientRect().left
      const maxD = levels[0]?.depth ?? depth
      const minD = levels[levels.length - 1]?.depth ?? depth
      let d = Math.floor((e.clientX - treeLeft) / INDENT)
      d = Math.max(minD, Math.min(maxD, d))
      const target = levels.find((l) => l.depth === d) || levels[0]
      setOver({ zone: 'after', target, depth: d })
    } else {
      setOver({ zone })
    }
  }

  const handleDrop = (e) => {
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

  return (
    <li>
      <div
        className={cls.join(' ')}
        draggable
        onDragStart={(e) => { e.stopPropagation(); setDrag(node.id); e.dataTransfer.effectAllowed = 'move' }}
        onDragEnd={() => { setDrag(null); setOver(null) }}
        onDragOver={handleDragOver}
        onDragLeave={() => setOver(null)}
        onDrop={handleDrop}
        onClick={(e) => onSelect(node, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey })}
        onContextMenu={(e) => { e.preventDefault(); onContext(e.clientX, e.clientY, node) }}
      >
        <span className={node.is_folder ? 'name folder' : 'name leaf'}>
          {node.is_folder ? '📁' : '📄'} {node.name}
        </span>
      </div>
      {/* level-aware drop guide for the "after" gap (indented to the chosen level,
          with a pill naming the destination folder so the level is obvious) */}
      {over?.zone === 'after' && (
        <div className="drop-guide" style={{ marginLeft: `${(over.depth - depth) * INDENT}px` }}>
          <span className="drop-guide-label">
            {over.target.parentName ? `→ ${over.target.parentName}` : '→ oberste Ebene'}
          </span>
        </div>
      )}
      {node.children?.length > 0 && (
        <ul>
          {node.children.map((c, i) => (
            <TreeNode key={c.id} node={c} parentId={node.id} index={i} depth={depth + 1}
              selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
              onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function Tree({ node, selectedIds, primaryId, onSelect, onContext, onMove, onMoveMany, levelsFor }) {
  // `node` is the implicit root container — don't render it; show its children.
  const [drag, setDrag] = useState(null)
  const dropOnRoot = (e) => {
    if (!drag) return
    e.preventDefault()
    if (selectedIds.includes(drag) && selectedIds.length > 1) onMoveMany(selectedIds, node.id, null)
    else onMove(drag, node.id, null)
    setDrag(null)
  }
  return (
    <ul
      className="tree"
      onDragOver={(e) => { if (drag) e.preventDefault() }}
      onDrop={dropOnRoot}
    >
      {(node.children ?? []).map((c, i) => (
        <TreeNode key={c.id} node={c} parentId={node.id} index={i} depth={0}
          selectedIds={selectedIds} primaryId={primaryId} onSelect={onSelect} onContext={onContext}
          onMove={onMove} onMoveMany={onMoveMany} levelsFor={levelsFor} drag={drag} setDrag={setDrag} />
      ))}
    </ul>
  )
}
